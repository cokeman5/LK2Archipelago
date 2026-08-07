"""
Shared constants and helper function used by the card-randomization
mechanics (mechanic_shop_contents, mechanic_starting_deck,
mechanic_bonus_draws, mechanic_magic_stone_costs).

Ported directly from LK2Generator.py - values/logic unchanged, just
consolidated here once instead of duplicated across each mechanic file.
"""
from worlds.LostKingdoms2 import *

CARD_INFO_TABLE_ADDRESS = 0x80732be0
CARD_SHOP_ADDRESS = 0x80168700
STARTING_DECK_ADDRESS = 0x80152640
BONUS_DRAW_ADDRESS = 0x80168168


def get_card_weights(cards, is_weighted: bool, target_cost: int, bias: int = 3) -> list:
    weights = []
    for card_name in cards:
        if is_weighted:
            weights.append(1 / (abs(lost_kingdoms_2_cards[card_name]["mana_cost"] - target_cost) + bias))
        else:
            weights.append(1)
    return weights
