"""
Card weighting shared by the card-randomization mechanics
(mechanic_randomize_shop_contents, mechanic_randomize_starting_deck,
mechanic_randomize_bonus_draws).

Randomly chosen cards are weighted by how close their magic stone cost is to
a target, so an early shop slot tends to offer cheap cards and a late one
expensive cards, instead of every slot being a uniform draw.

Costs are read from rune.pdm as it currently stands in the ISO. They cannot
come from a static table: mechanic_randomize_magic_stone_costs may have
randomized, shuffled or scaled them, and weighting by the vanilla numbers
would then describe a game other than the one being built.
"""
import logging

from worlds.LostKingdoms2 import lost_kingdoms_2_cards

from .stats_database import StatsDatabase

logger = logging.getLogger("Lost Kingdoms 2")

DEFAULT_BIAS = 3

# {card_name: magic stone cost} for the current patch run, alongside the
# patcher it was built from so a later run cannot inherit stale values.
_cached_patcher = None
_cached_costs = None


def reset_card_cost_cache():
    """Forget the cached costs.

    Needed only if magic stone costs are written after weights have already
    been requested; the cache would otherwise hold the values as they stood
    at first use.
    """
    global _cached_patcher, _cached_costs
    _cached_patcher = None
    _cached_costs = None


def get_card_id(card_name: str):
    """The card's own id, or None if the entry has no usable one.

    hexCode is that id as a hex string - the same value the mechanics write
    into the shop, starting deck and bonus draw tables to name a card.
    """
    hex_code = lost_kingdoms_2_cards.get(card_name, {}).get("hexCode")
    if hex_code is None:
        return None
    try:
        return int(hex_code, 16)
    except (TypeError, ValueError):
        return None


def get_magic_stone_costs(patcher) -> dict:
    """{card_name: magic stone cost} read from the ISO.

    Must run AFTER magic stone costs are written. ISO_Patcher applies that
    mechanic before the three consumers here, so the ordering holds; the
    result is then cached, because rune.pdm is ~1.2MB and the shop mechanic
    asks for weights once per slot.
    """
    global _cached_patcher, _cached_costs
    if _cached_costs is not None and _cached_patcher is patcher:
        return _cached_costs

    database = StatsDatabase(patcher)
    known = set(database.card_ids)

    costs = {}
    missing = []
    for card_name in lost_kingdoms_2_cards:
        card_id = get_card_id(card_name)
        if card_id is None or card_id not in known:
            missing.append(card_name)
            continue
        costs[card_name] = database.read(card_id, "magic_stone_cost")

    if missing:
        # Not fatal - these cards simply weigh as though they cost nothing.
        # Worth reporting, because a card silently missing from the stat
        # table would otherwise skew every draw it takes part in.
        logger.info(
            f"[card weights] {len(missing)} card(s) have no stat table entry "
            f"and will weigh as cost 0: {', '.join(sorted(missing)[:8])}"
            + (" ..." if len(missing) > 8 else "")
        )

    _cached_patcher = patcher
    _cached_costs = costs
    return costs


def get_card_weights(cards, is_weighted: bool, target_cost: int,
                     bias: int = DEFAULT_BIAS, patcher=None) -> list:
    """One weight per card, favouring costs near target_cost.

    bias flattens the curve: the weight is 1 / (distance + bias), so a larger
    bias makes far-from-target cards relatively more likely. Without it a card
    sitting exactly on the target would divide by zero.

    patcher is required when is_weighted is set, since costs come from the
    ISO. Unweighted callers can omit it - every card simply weighs 1.
    """
    if not is_weighted:
        return [1] * len(cards)

    if patcher is None:
        raise ValueError(
            "get_card_weights needs a patcher when is_weighted is set: magic "
            "stone costs are read from rune.pdm so that the weights follow "
            "any randomization applied to them."
        )

    costs = get_magic_stone_costs(patcher)
    return [
        1 / (abs(costs.get(card_name, 0) - target_cost) + bias)
        for card_name in cards
    ]