from __future__ import annotations

from dataclasses import dataclass
from Options import Choice, Option, PerGameCommonOptions, Range, DeathLink, Toggle

from typing import Dict

class WinConditionOption(Choice):
    """Choose the win condition."""
    display_name = "Win Condition"
    option_defeat_god_of_harmony = 0
    option_defeat_emperor = 1
    option_collect_all_cards = 2
    default = 0

class FairysanityConditionOption(Toggle):
    """Choose whether Red Fairies are added to the pool"""
    display_name = "Fairysanity"
    default = 1

class ShopsanityConditionOption(Toggle):
    """Choose whether cards in the shop becomes AP items."""
    display_name = "Shopsanity"
    default = 0

class CombosanityConditionOption(Toggle):
    """Choose whether to add combos as checks."""
    display_name = "Combosanity"
    default = 0

class OpenWorldConditionOption(Toggle):
    """Choose whether all levels are unlocked from the start."""
    display_name = "Open World"


@dataclass
class LostKingdoms2Options(PerGameCommonOptions):
    win_condition : WinConditionOption
    fairysanity : FairysanityConditionOption
    shopsanity: ShopsanityConditionOption
    combosanity: CombosanityConditionOption
    open_world : OpenWorldConditionOption
    death_link: DeathLink