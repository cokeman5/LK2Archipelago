"""
Randomizes each card's magic stone (mana) cost (ported from
LK2Generator.py's randomize_magic_stone_costs - logic/values unchanged).

Note: this mutates lost_kingdoms_2_cards[card_name]["mana_cost"] in place,
which the other three card-randomization mechanics' weighting logic
(get_card_weights) depends on - this must run before
mechanic_starting_deck/mechanic_shop_contents/mechanic_bonus_draws for their
weighted randomization to reflect the newly-randomized costs, matching the
original code's call order (already preserved in ISO_Patcher._apply_mechanics).
"""
import random
import logging

from worlds.LostKingdoms2 import *
from .card_randomizer_helpers import CARD_INFO_TABLE_ADDRESS

logger = logging.getLogger()


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1) + 3)
    for card_name in sorted(lost_kingdoms_2_cards):
        new_mana_cost = random.randint(1, 15)
        # Mana cost is 1 byte
        patcher.patch_value(CARD_INFO_TABLE_ADDRESS + 352 * lost_kingdoms_2_cards[card_name][
            "orderInMemory"] + 226, new_mana_cost, 1)
        lost_kingdoms_2_cards[card_name]["mana_cost"] = new_mana_cost
        logger.info("Setting " + str(card_name) + " mana cost to " + str(new_mana_cost))
