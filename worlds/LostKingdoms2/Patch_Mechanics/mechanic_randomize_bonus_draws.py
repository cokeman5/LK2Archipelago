"""
Randomizes bonus draw cards (ported from LK2Generator.py's
randomize_bonus_draws - logic/values unchanged).
"""
import random

from worlds.LostKingdoms2 import *
from .card_randomizer_helpers import get_card_weights, BONUS_DRAW_ADDRESS


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1) + 2)
    cards = sorted(list(lost_kingdoms_2_cards.keys()))
    excluded_cards = lost_kingdoms_2_flying_cards + lost_kingdoms_2_jumping_cards + ["God of Destruction"] + [
        "Stone Golem"]
    cards = sorted(list(set(cards) - set(excluded_cards)))
    group_dict = {}

    for key in lost_kingdoms_2_bonus_draws:
        bonus_draw = lost_kingdoms_2_bonus_draws[key]
        if group_dict.get(bonus_draw["cardGroup"], 0):
            card_name = group_dict.get(bonus_draw["cardGroup"])
            patcher.patch_value(BONUS_DRAW_ADDRESS + int(bonus_draw["address"], 16) - 0x183169,
                                 int(lost_kingdoms_2_cards[card_name]["hexCode"], 16), 2)
        else:
            weights = get_card_weights(cards, output_data.get("randomize_bonus_draws", 0) == 1,
                                        bonus_draw["cardGroup"] // 5)
            card_name = random.choices(cards, weights=weights, k=1)[0]
            cards.remove(card_name)
            patcher.patch_value(BONUS_DRAW_ADDRESS + int(bonus_draw["address"], 16) - 0x183169,
                                 int(lost_kingdoms_2_cards[card_name]["hexCode"], 16), 2)
            group_dict[bonus_draw["cardGroup"]] = card_name
