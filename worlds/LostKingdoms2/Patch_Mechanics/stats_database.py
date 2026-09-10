"""
stats_database.py - read/write the per-card and per-monster stat table.

Card stats live in "game/rune.pdm", loaded verbatim to DAT_802e9400, so
    runtime_address = <value at 0x802E9400> + file_offset

Two tables, same layout, different contents for the same card:
    ctm2 (header +0x10) - the player's card   - 226 cards
    ctm  (header +0x14) - the enemy monster   - 218 cards, 197 shared
Which one the game reads depends on the accessor: GetCardData2 -> ctm2
(element, rarity, type, price, buy/sell/copy, effect text), GetCardData ->
ctm (summon effect category/variant/stat value). The card details screen
draws both, one section each.

Lookup mirrors GetCardData2 - an offset table, not a stride array:
    entry = block + u32_at(block + 8 + card_id*4)      0 = no data
Entries happen to be contiguous 0x160 blocks, but always go through the
offset table; a card's array position is not its id.

Each card also has 2 skill blocks of 0x48 bytes at entry + n*0x48.

Patching is a plain ISO edit - no code cave, no hooks.

Import StatsDatabase from a mechanic and use read()/write(), or the
randomize_field()/shuffle_field() helpers for whole-table operations.
"""

import logging
import struct

logger = logging.getLogger(__name__)

RUNE_PDM_ISO_OFFSET = 0x6783A00
RUNE_PDM_SIZE = 0x120780

CTM2_BLOCK_OFFSET = 0x000CEC80      # player-card table
CTM1_BLOCK_OFFSET = 0x000E2800      # enemy-monster table
CARD_OFFSET_TABLE_START = 0x8
CARD_ID_MIN, CARD_ID_MAX = 1, 299
CARD_ENTRY_SIZE = 0x160
SKILL_STRIDE = 0x48
SKILL_COUNT = 2                     # slot 2's accessors alias card data

ELEMENTS = {0: "fire", 1: "water", 2: "earth", 3: "wood", 4: "neutral", 5: "mech"}

CARD_TYPES = {
    0: "independent",   # allied monster: collision, health, lifespan
    1: "helper",        # same entity machinery, but buffs/debuffs/heals
    2: "summon",        # one-shot, pick 1 of 2 effects, no collision/health
    3: "weapon",        # quick, no choice, several uses
    4: "transform",     # player becomes it; own health bar, 2 attacks
}

STATUSES = {
    0: "poison", 1: "paralysis", 2: "curse", 3: "charmed", 4: "petrify",
    5: "sleep", 6: "instant_death", 7: "acid", 8: "knockdown",
}
# 0-5 are timed and have entity timer slots; 6-8 fire once and have none.
# acid = instant kill vs mech. knockdown is probable: always 100%, unresisted.

# Behaviour class at card field "creature_class" - finer than card type and
# what actually drives the AI. Classes 8 and 11 never appear in card data
# (non-card entities; 11 is likely the player).
CREATURE_CLASSES = {
    0: "ai_creature", 1: "summon", 2: "weapon_a", 3: "weapon_b",
    4: "weapon_c", 5: "helper_a", 6: "mixed_a", 7: "helper_b",
    9: "mixed_b", 10: "transform",
}

# --- field tables ---------------------------------------------------------
# offset/size describe the LIVE bytes - where a declared field is wider than
# the range actually used, offset/size point at the used part and `declared`
# records the original. count/stride describe arrays. `enum` links to a table
# above. Sizes are 1, 2 or 4 and always big-endian.

SKILL_FIELDS = {
    "name":              {"offset": 0x00, "size": 0, "note": "Shift-JIS, NUL-terminated"},
    "context_param":     {"offset": 0x2A, "size": 2, "note": "float-converted into entity context"},
    "power":             {"offset": 0x2E, "size": 2, "declared": (0x2C, 4), "note": "the ATK shown on the card screen"},
    "anim_param":        {"offset": 0x30, "size": 1, "note": "also indexed by animation id"},
    "defence_term":      {"offset": 0x31, "size": 1, "note": "feeds the damage calc"},
    "kind":              {"offset": 0x32, "size": 1, "note": "0 = plain attack, else a named skill"},
    "drain":             {"offset": 0x33, "size": 1, "note": "percent, heal/drain"},
    "status_flags":      {"offset": 0x34, "size": 1, "count": 9, "stride": 1, "enum": STATUSES},
    "status_chance":     {"offset": 0x40, "size": 1, "note": "percent; forced to 100 for knockdown"},
    "flag_41":           {"offset": 0x41, "size": 1},
    "self_hp_cost":      {"offset": 0x42, "size": 1, "note": "drains the user's own HP"},
    "unread_43":         {"offset": 0x43, "size": 1, "note": "set on 189 cards, no code reads it"},
    "hit_weight":        {"offset": 0x44, "size": 1, "note": "0-4, picks impact sound 0x11/0x12/0x13"},
    "disable_flag":      {"offset": 0x45, "size": 1, "note": "non-zero disables something"},
    "cooldown_reduction": {"offset": 0x46, "size": 1, "note": "subtracted from target cooldown"},
    "combo_gate":        {"offset": 0x47, "size": 1, "note": "gates a post-animation random roll"},
}

CARD_FIELDS = {
    "upgrade_target":    {"offset": 0x90, "size": 2, "count": 4, "stride": 4, "note": "target card id"},
    "upgrade_xp_cost":   {"offset": 0x92, "size": 2, "count": 4, "stride": 4},
    "name_jp":           {"offset": 0xA0, "size": 0, "note": "Shift-JIS, NUL-terminated, <=22 bytes"},
    "card_id_self":      {"offset": 0xC0, "size": 2, "note": "equals the lookup id on every card"},
    "sort_key":          {"offset": 0xC2, "size": 2, "note": "dense 1..226 catalogue order"},
    "max_health":        {"offset": 0xC6, "size": 2, "declared": (0xC4, 4)},
    "defense":           {"offset": 0xCB, "size": 1, "declared": (0xC8, 4)},
    "status_resist":     {"offset": 0xD0, "size": 1, "count": 9, "stride": 1, "enum": STATUSES,
                          "note": "defender side, percent"},
    "creature_class":    {"offset": 0xDC, "size": 1, "enum": CREATURE_CLASSES},
    "element":           {"offset": 0xDD, "size": 1, "enum": ELEMENTS},
    "lifespan":          {"offset": 0xDE, "size": 2, "note": "on-field timer; 0 for summon/weapon"},
    "uses":              {"offset": 0xE1, "size": 1, "note": "types 2/3 only (summon 1, weapon 2-5)"},
    "magic_stone_cost":  {"offset": 0xE2, "size": 1},
    "copy_exp_cost":     {"offset": 0xE4, "size": 2, "note": "XP to duplicate the card"},
    "price":             {"offset": 0xE6, "size": 2, "note": "buy and sell both read this"},
    "rarity":            {"offset": 0xE8, "size": 1, "note": "0-8, the star level"},
    "size_scale":        {"offset": 0xE9, "size": 1},
    "size_x":            {"offset": 0xEC, "size": 2},
    "size_y":            {"offset": 0xEE, "size": 2},
    "move_param":        {"offset": 0xF0, "size": 2, "note": "velocity-related, not a dimension"},
    "attack_range_a":    {"offset": 0xF4, "size": 4},
    "attack_range_max":  {"offset": 0xF8, "size": 4},
    "attack_range_min":  {"offset": 0xFC, "size": 2},
    "attack_cooldown":   {"offset": 0x104, "size": 1},
    "context_angle_a":   {"offset": 0x106, "size": 1},
    "context_angle_b":   {"offset": 0x107, "size": 1},
    "ai_action_chance":  {"offset": 0x108, "size": 1, "note": "percent, rolled against rand()%100"},
    "dramatic_camera":   {"offset": 0x10A, "size": 1},
    "helper_effect_id":  {"offset": 0x110, "size": 1, "note": "which helper effect; game zeroes it at runtime"},
    "card_type":         {"offset": 0x111, "size": 1, "enum": CARD_TYPES},
    "no_attack_hit":     {"offset": 0x113, "size": 1, "note": "skips ApplyAttackHitAndSpark"},
    "flee_distance_b":   {"offset": 0x134, "size": 4, "note": "always 0 in vanilla"},
    "flee_distance":     {"offset": 0x138, "size": 4, "note": "only on fleeing/stand-off creatures"},
    "size_x2":           {"offset": 0x13C, "size": 2},
    "size_z":            {"offset": 0x13E, "size": 2},
}

# Ranges to leave alone:
#   0x114..0x133  runtime scratch - the spawn path memsets it
#   0x154..0x15F  build garbage (b'_NT\x00Os2LibPa' on every entry)
#   0x102         populated but no code reads it

# Decompiled names that are wrong, so they are not trusted again:
#   GetCardMagicCost   -> copy_exp_cost      GetCardDefenseStat -> price
#   GetCardTypeVariant -> magic_stone_cost   GetCardStatModifierA/B -> upgrades

# How a stat randomizer option behaves. Shared by the mechanics and by
# ISO_Patcher so the meaning of the option value is defined in exactly one
# place. OFF is not the same as "do nothing": a multiplier still applies to
# the vanilla values, which is how a player scales prices or costs without
# randomizing them at all.
MODE_OFF = 0
MODE_RANDOMIZE = 1
MODE_SHUFFLE = 2

_FMT = {1: ">B", 2: ">H", 4: ">I"}


class StatsDatabase:
    """The card stat table in rune.pdm, addressed by card id and field name.

    Reads the file straight out of the ISO through the patcher unless `data`
    is supplied. Writes go to the ISO and to the in-memory copy, so chained
    operations see each other's results - scale_field() after shuffle_field()
    scales the shuffled values, not the vanilla ones. `vanilla` keeps the
    untouched bytes if the originals are needed.
    """

    def __init__(self, patcher, data=None, block=CTM2_BLOCK_OFFSET):
        self.patcher = patcher
        self.block = block
        raw = data if data is not None else self._read_from_iso(patcher)
        self.vanilla = bytes(raw)
        self.data = bytearray(raw)
        self.entries = {cid: off for cid, off in self._iter_entries()}

    @staticmethod
    def _read_from_iso(patcher):
        pos = patcher.file.tell()
        try:
            patcher.file.seek(RUNE_PDM_ISO_OFFSET)
            data = patcher.file.read(RUNE_PDM_SIZE)
        finally:
            patcher.file.seek(pos)
        if len(data) != RUNE_PDM_SIZE:
            raise ValueError(f"read {len(data)} bytes of rune.pdm, expected {RUNE_PDM_SIZE}")
        return data

    def _iter_entries(self):
        for cid in range(CARD_ID_MIN, CARD_ID_MAX + 1):
            slot = self.block + CARD_OFFSET_TABLE_START + cid * 4
            rel = struct.unpack_from(">I", self.data, slot)[0]
            if rel:
                yield cid, self.block + rel

    @property
    def card_ids(self):
        """Every card id with data, ascending."""
        return sorted(self.entries)

    def _entry(self, card_id):
        try:
            return self.entries[card_id]
        except KeyError:
            raise KeyError(f"card {card_id} has no entry in this table") from None

    @staticmethod
    def _resolve(name, index, skill):
        table = SKILL_FIELDS if skill is not None else CARD_FIELDS
        if name not in table:
            raise KeyError(f"unknown {'skill' if skill is not None else 'card'} field {name!r}")
        f = table[name]
        if not f["size"]:
            raise ValueError(f"{name!r} is a string field - use read_string()")
        off = f["offset"]
        if "count" in f:
            if index is None:
                raise ValueError(f"{name!r} is an array of {f['count']} - pass index=")
            if not 0 <= index < f["count"]:
                raise IndexError(f"{name!r} index {index} out of range")
            off += index * f["stride"]
        elif index is not None:
            raise ValueError(f"{name!r} is not an array")
        if skill is not None:
            if not 0 <= skill < SKILL_COUNT:
                raise IndexError(f"skill {skill} out of range")
            off += skill * SKILL_STRIDE
        return f, off

    def read(self, card_id, name, index=None, skill=None, raw=False):
        """Field value. Returns the enum label where the field has one, unless
        raw=True."""
        f, off = self._resolve(name, index, skill)
        val = struct.unpack_from(_FMT[f["size"]], self.data, self._entry(card_id) + off)[0]
        enum = f.get("enum")
        if enum and "count" not in f and not raw:
            return enum.get(val, val)
        return val

    def read_string(self, card_id, name, skill=None):
        """One of the two Shift-JIS name fields."""
        table = SKILL_FIELDS if skill is not None else CARD_FIELDS
        off = table[name]["offset"] + (skill * SKILL_STRIDE if skill is not None else 0)
        start = self._entry(card_id) + off
        raw = bytes(self.data[start:start + 0x2C]).split(b"\x00")[0]
        return raw.decode("shift_jis", "replace")

    def read_array(self, card_id, name, skill=None, raw=False):
        table = SKILL_FIELDS if skill is not None else CARD_FIELDS
        return [self.read(card_id, name, i, skill, raw)
                for i in range(table[name]["count"])]

    def upgrades(self, card_id):
        """[(target_card_id, xp_cost), ...] - up to 4. Every target in the
        vanilla file is a valid card id; keep it that way when patching."""
        return [(t, c) for t, c in zip(self.read_array(card_id, "upgrade_target"),
                                       self.read_array(card_id, "upgrade_xp_cost")) if t]

    def statuses(self, card_id, skill):
        """Names of the statuses a skill inflicts."""
        return [STATUSES[i] for i, v in
                enumerate(self.read_array(card_id, "status_flags", skill)) if v == 1]

    def write(self, card_id, name, value, index=None, skill=None):
        """Patch one field into the ISO."""
        entry = self._entry(card_id)

        # Every entry stores its own id at +0xC0; a mismatch means the offset
        # arithmetic is wrong and we would corrupt a different card.
        stored = struct.unpack_from(">H", self.data,
                                    entry + CARD_FIELDS["card_id_self"]["offset"])[0]
        if stored != card_id:
            raise ValueError(f"integrity check failed for card {card_id}: +0xC0 holds {stored}")

        f, off = self._resolve(name, index, skill)
        if not 0 <= value < 1 << (8 * f["size"]):
            raise ValueError(f"{value} does not fit in {f['size']} byte(s) for {name!r}")

        # rune.pdm is a standalone file in the ISO, not part of main.dol, so
        # its bytes are written directly. patch_value() must NOT be used here:
        # it treats its argument as a RAM address and resolves it through
        # ram_to_iso(), which fails for anything outside a DOL section.
        packed = struct.pack(_FMT[f["size"]], value)
        self.patcher.file.seek(RUNE_PDM_ISO_OFFSET + entry + off)
        self.patcher.file.write(packed)
        struct.pack_into(_FMT[f["size"]], self.data, entry + off, value)

    def slots(self, name, skill=None, skip_zero=False, gated_by=None, card_ids=None):
        """Which (card_id, index) pairs an operation should touch.

        index is None for a plain field. `skip_zero` leaves cards whose value
        is already 0 alone - use it for fields where 0 means "not available"
        (a price of 0 is an unbuyable card, a copy cost of 0 an uncopyable
        one). `gated_by` names a parallel array that must be non-zero at the
        same index - upgrade_xp_cost is only meaningful where upgrade_target
        points somewhere.
        """
        table = SKILL_FIELDS if skill is not None else CARD_FIELDS
        count = table[name].get("count")
        out = []
        for cid in (self.card_ids if card_ids is None else card_ids):
            for i in (range(count) if count else [None]):
                if gated_by and not self.read(cid, gated_by, i, skill, raw=True):
                    continue
                if skip_zero and not self.read(cid, name, i, skill, raw=True):
                    continue
                out.append((cid, i))
        return out

    def _slots_or_all(self, name, skill, slots):
        return self.slots(name, skill) if slots is None else list(slots)

    def randomize_field(self, name, minimum, maximum, rng, skill=None, slots=None):
        """Roll each slot independently in [minimum, maximum].

        Returns {(card_id, index): new_value}.
        """
        f, _ = self._resolve(name, 0 if "count" in (SKILL_FIELDS if skill is not None
                                                    else CARD_FIELDS)[name] else None, skill)
        limit = (1 << (8 * f["size"])) - 1
        if not 0 <= minimum <= maximum <= limit:
            raise ValueError(f"range {minimum}..{maximum} invalid for {name!r} "
                             f"(field holds 0..{limit})")
        result = {}
        for cid, idx in self._slots_or_all(name, skill, slots):
            value = rng.randint(minimum, maximum)
            self.write(cid, name, value, idx, skill)
            result[(cid, idx)] = value
        return result

    def shuffle_field(self, name, rng, skill=None, slots=None):
        """Redeal the existing values among the slots.

        The values are collected as a LIST, not a set - duplicates are kept, so
        the distribution is identical to vanilla and only the assignment moves.

        Returns {(card_id, index): new_value}.
        """
        targets = self._slots_or_all(name, skill, slots)
        values = [self.read(cid, name, idx, skill, raw=True) for cid, idx in targets]
        rng.shuffle(values)
        result = {}
        for (cid, idx), value in zip(targets, values):
            self.write(cid, name, value, idx, skill)
            result[(cid, idx)] = value
        return result

    def scale_field(self, name, multiplier, skill=None, slots=None):
        """Multiply each slot's current value by `multiplier` and floor it.

        Reads whatever is in the table now, so running this after
        randomize_field() or shuffle_field() scales those results. Values that
        would overflow the field are clamped to its maximum and counted in the
        log rather than silently wrapping.

        Returns {(card_id, index): new_value}.
        """
        if multiplier < 0:
            raise ValueError(f"multiplier {multiplier} must not be negative")
        table = SKILL_FIELDS if skill is not None else CARD_FIELDS
        f, _ = self._resolve(name, 0 if "count" in table[name] else None, skill)
        limit = (1 << (8 * f["size"])) - 1
        result, clamped = {}, 0
        for cid, idx in self._slots_or_all(name, skill, slots):
            value = int(self.read(cid, name, idx, skill, raw=True) * multiplier)
            if value > limit:
                value = limit
                clamped += 1
            self.write(cid, name, value, idx, skill)
            result[(cid, idx)] = value
        if clamped:
            logger.warning(f"[stats_database] {name!r} x{multiplier}: {clamped} value(s) "
                           f"clamped to the field maximum {limit}")
        return result