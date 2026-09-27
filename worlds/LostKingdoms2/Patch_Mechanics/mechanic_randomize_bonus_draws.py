"""
Randomizes the cards offered by each level's end-of-mission reward screen.

The screen shows six draws, read from levelExtraCardTable. A row repeats card
ids across its six slots, so a level usually offers fewer than six DIFFERENT
cards - lost_kingdoms_2_bonussanity has one entry per distinct card, carrying
every slot address that holds it.

Every address in an entry gets the SAME new id. Writing to only some of them
would split a group: the screen would start offering a card no location
represents, and the location would no longer match what the player sees. The
previous table expressed this with a "cardGroup" column and a running
dictionary; grouping by distinct card makes it implicit, so the bookkeeping is
gone.

Two other things changed with the table. Addresses are now RAM addresses ready
for patch_value, so the old BONUS_DRAW_ADDRESS + offset - 0x183169 arithmetic
is no longer needed. And the Proving Grounds are included, which the old table
omitted entirely - those twenty floors are the only rows with six genuinely
distinct cards, so they take six entries each.
"""
import random

from worlds.LostKingdoms2 import *
from .card_randomizer_helpers import get_card_weights

# How many entries share a target magic stone cost. The old table derived this
# from its cardGroup column as `cardGroup // 5`, with groups numbered
# sequentially through the game, so the target rose as the player progressed
# and rarer draws within a level cost more than common ones. Counting entries
# in table order reproduces that exactly for the levels the old table covered.
ENTRIES_PER_COST_STEP = 5


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1) + 2)

    excluded_cards = (
        lost_kingdoms_2_flying_cards
        + lost_kingdoms_2_jumping_cards
        + ["God of Destruction", "Stone Golem"]
    )
    cards = sorted(set(lost_kingdoms_2_cards) - set(excluded_cards))

    draws = list(lost_kingdoms_2_bonussanity.values())
    if len(draws) > len(cards):
        raise ValueError(
            f"{len(draws)} bonus draws need {len(draws)} distinct cards but "
            f"only {len(cards)} are available after exclusions. Either allow "
            f"repeats or narrow the exclusion list."
        )

    is_weighted = output_data.get("randomize_bonus_draws", 0) == 1

    for number, draw in enumerate(draws, start=1):
        weights = get_card_weights(
            cards, is_weighted, number // ENTRIES_PER_COST_STEP, patcher=patcher
        )
        card_name = random.choices(cards, weights=weights, k=1)[0]
        cards.remove(card_name)

        card_id = int(lost_kingdoms_2_cards[card_name]["hexCode"], 16)
        for address in draw["addresses"]:
            patcher.patch_value(int(address, 16), card_id, 2)