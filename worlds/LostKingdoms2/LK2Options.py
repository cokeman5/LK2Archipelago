from __future__ import annotations

from dataclasses import dataclass
from Options import Choice, Option, PerGameCommonOptions, Range, DeathLink, Toggle, Visibility

class WinConditionOption(Choice):
    """Choose the win condition.
    Warning: Emperor win condition may be bugged right now.
    Baseline: 175 locations, 175 items"""
    display_name = "Win Condition"
    option_defeat_god_of_harmony = 0
    option_defeat_emperor = 1
    option_collect_red_fairies = 2
    #option_collect_all_cards = 3
    default = 0

class CollectRedFariesAmount(Range):
    """How many red fairies you need to goal.
    Only relevant if your goal is collecting red fairies."""
    display_name = "Collect Red Fairies Amount"
    range_start = 1
    range_end = 97
    default = 50

class FairysanityConditionOption(Toggle):
    """Choose whether Red Fairies are added to the pool.
    +100 locations, +100 items."""
    display_name = "Fairysanity"
    default = 1

class ShopsanityConditionOption(Toggle):
    """Choose whether cards in the shop becomes AP items."""
    visibility = Visibility.none
    display_name = "Shopsanity"
    default = 0

class CombosanityConditionOption(Toggle):
    """Choose whether to add combos as checks.
    +40 locations."""
    display_name = "Combosanity"
    default = 0

class EnemysanityConditionOption(Choice):
    """Choose whether to make every single unique enemy kill a check.
    Be warned that spawn triggers in this game are very unintuitive, hidden, and
    once a level is beaten it will have new enemy spawns. Please report any issue you encounter.
    Enemysanity Plus includes all the enemies in the Proving Grounds.
    +547 locations. Enemysanity Plus: additional +405"""
    display_name = "Enemysanity"
    option_disabled = 0
    option_enemysanity = 1
    option_enemysanity_plus = 2
    default = 0

class ProgressiveLevelingOption(Toggle):
    """Choose whether to have character levels as a progressive item. You will no longer be able to level up normally.
    +19 items"""
    display_name = "Progressive Leveling"
    default = 0

class ProgressiveAttributeProficienciesOption(Toggle):
    """Choose whether to have character levels as a progressive item. You will no longer be able to level up normally.
    +34 items"""
    display_name = "Progressive Leveling"
    default = 0

class OpenWorldConditionOption(Toggle):
    """Choose whether all levels are unlocked from the start."""
    visibility = Visibility.none
    display_name = "Open World"
    default = 0

class ExcludeSacredBattleArenaChecksOption(Toggle):
    """By enabling, prevents the checks in the sacred battle arenas from being progressive.(There are still checks)"""
    display_name = "Exclude Sacred Battle Checks"
    default = 0

class RandomizeStartingDeck(Choice):
    """
    Choose whether to randomize your starting deck.
    Off = Vanilla, no randomization of the starting deck.
    Weighted Random = Randomized, with a much higher chance to get cards with low magic costs. (No key cards)
    Fully Random = Randomized; every card is equally likely to appear in your starting deck. (No key cards)
    """
    display_name = "Randomize Starting Deck"
    option_off = 0
    option_weighted_random = 1
    option_fully_random = 2
    default = 1

class RandomizeShopContents(Choice):
    """
    Choose whether to randomize what cards appear in the shops.
    Off = Vanilla, no randomization of the shops' contents.
    Weighted Random = Randomized. Early shops are more likely to have low magic cost cards, later shops are more likely to have higher cost cards. (No key cards)
    Fully Random = Randomized; every card is equally likely to appear in the shop. (No key cards)
    """
    display_name = "Randomize Shop Contents"
    option_off = 0
    option_weighted_random = 1
    option_fully_random = 2
    default = 1

class RandomizeBonusDraws(Choice):
    """
    Choose whether to randomize the contents of the bonus draws at the end of each level.
    Off = Vanilla, no randomization of the bonus draw.
    Weighted Random = Randomized. Early bonus are more likely to have low magic cost cards, later bonus draw are more likely to have higher cost cards. (No key cards)
    Fully Random = Randomized; every card is equally likely to appear in the bonus draws. (No key cards).
    """
    display_name = "Randomize Bonus Draws"
    option_off = 0
    option_weighted_random = 1
    option_fully_random = 2
    default = 1

class RandomizeEnemies(Toggle):
    """Choose to randomize every non-unique monster in the game. Every instance of monster X will become monster Y.
    Still very experimental, so play at your own risk. If the game crashes, lags, or becomes corrupted; please report
    with logs."""
    display_name = "Randomize Enemies"
    default = 0

class RandomizeMagicCosts(Toggle):
    """Choose to randomize the magic stone cost of every card to between 1-15. Warning: This can trivialize the game"""
    display_name = "Randomize Magic Costs"
    default = 0

class LevelRandomization(Toggle):
    """Randomize which levels unlock when you would normally unlock a level.
    Note: Alenjah Castle still always leads to all the towers in order, and
    the sacred battle arena still leads to sacred battle arena 2."""

    display_name = "Level Randomization"
    default = 0

class MusicRandomization(Toggle):
    """Randomize the music that plays during levels"""
    display_name = "Level Music Randomization"
    default = 0

class CharacterModel(Choice):
    """Change your character model.
    Note: Models other than Tara do not have injured animations, and therefor are mechanically better.
    """
    display_name = "Character Model"
    option_Tara = 0
    option_Rashiannu = 1
    option_Leod = 2
    option_Katia = 3
    option_Helena = 4
    option_Thalnos = 5
    option_Stranger = 6
    option_Kendarie_Soldier = 7
    option_Tara_Alt = 8
    option_Rashiannu_Alt = 9
    option_Leod_Alt = 10
    option_Katia_Alt = 11
    option_Helena_Alt = 12
    option_Thalnos_Alt = 13
    option_Stranger_Alt = 14
    option_Kendarie_Soldier_Alt = 15
    default = 0


@dataclass
class LostKingdoms2Options(PerGameCommonOptions):
    win_condition : WinConditionOption
    collect_red_fairies_amount : CollectRedFariesAmount
    fairysanity : FairysanityConditionOption
    shopsanity: ShopsanityConditionOption
    combosanity: CombosanityConditionOption
    enemysanity: EnemysanityConditionOption
    open_world : OpenWorldConditionOption
    exclude_sacred_battle_arena_checks: ExcludeSacredBattleArenaChecksOption
    death_link: DeathLink
    randomize_starting_deck : RandomizeStartingDeck
    randomize_shop_contents : RandomizeShopContents
    randomize_bonus_draws : RandomizeBonusDraws
    randomize_magic_stone_costs : RandomizeMagicCosts
    randomize_levels : LevelRandomization
    progressive_leveling: ProgressiveLevelingOption
    progressive_attribute_proficiencies: ProgressiveAttributeProficienciesOption
    character_model : CharacterModel
    randomize_enemies : RandomizeEnemies
    randomize_level_music : MusicRandomization