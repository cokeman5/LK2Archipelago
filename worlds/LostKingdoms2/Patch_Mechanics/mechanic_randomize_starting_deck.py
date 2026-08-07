"""
Randomizes the starting deck (ported from LK2Generator.py's
randomize_starting_deck - logic/values unchanged).
"""
import random

from worlds.LostKingdoms2 import *
from .card_randomizer_helpers import get_card_weights, STARTING_DECK_ADDRESS


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1) + 1)
    cards = sorted(list(lost_kingdoms_2_cards.keys()))
    excluded_cards = lost_kingdoms_2_flying_cards + lost_kingdoms_2_jumping_cards + ["God of Destruction"] + [
        "Stone Golem"]
    cards = sorted(list(set(cards) - set(excluded_cards)))

    for x in range(12):
        weights = get_card_weights(cards, output_data.get("randomize_starting_deck", 0) == 1, 1)
        card_name = random.choices(cards, weights=weights, k=1)[0]
        cards.remove(card_name)
        # Card IDs are 2 bytes
        patcher.patch_value(STARTING_DECK_ADDRESS + x * 2,
                             int(lost_kingdoms_2_cards[card_name]["hexCode"], 16), 2)
