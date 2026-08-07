"""
Randomizes the shop's card selection (ported from LK2Generator.py's
randomize_shop_contents - logic/values unchanged).
"""
import random
import logging

from worlds.LostKingdoms2 import *
from .card_randomizer_helpers import get_card_weights, CARD_SHOP_ADDRESS, CARD_INFO_TABLE_ADDRESS

logger = logging.getLogger()


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1))
    cards = sorted(list(lost_kingdoms_2_cards.keys()))
    excluded_cards = lost_kingdoms_2_flying_cards + lost_kingdoms_2_jumping_cards + ["God of Destruction"] + [
        "Stone Golem"]
    cards = sorted(list(set(cards) - set(excluded_cards)))

    for x in range(32):
        weights = get_card_weights(cards, output_data.get("randomize_shop_contents", 0) == 1, (x // 8) * 4)
        card_name = random.choices(cards, weights=weights, k=1)[0]
        logger.info("Card set to shop slot " + str(x) + ": " + card_name)
        # Card IDs are 2 bytes
        patcher.patch_value(CARD_SHOP_ADDRESS + x * 2,
                             int(lost_kingdoms_2_cards[card_name]["hexCode"], 16), 2)
        cards.remove(card_name)

    # Add custom prices for cards that lack prices
    for card in lostkingdoms_2_custom_prices:
        # Prices are usually 2 bytes
        patcher.patch_value(CARD_INFO_TABLE_ADDRESS + 230 + 22 * 16 * lost_kingdoms_2_cards[card][
            "orderInMemory"], lostkingdoms_2_custom_prices[card]["price"], 2)
