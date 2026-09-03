"""
Shared monster/card database for this APWorld's cross-level-monster
mechanics. A single source of truth for every card's name, its known
internal "sound ID" (which reliably differs from its own card ID -
confirmed via direct .pps file parsing for every entry currently
populated below - see each mechanic's own history/comments for the
full "why"), and, where investigated, which level file(s) it can be
found in as a donor and at what file offset/size within that file's
own resource table.

MAX_NORMAL_CARD_ID: derived directly from cards.txt's own highest
entry (Sacred Umpire, 0xe8). Any card ID above this value is a
"special" entity (e.g. the Stranger) that is never a normal, ownable
monster card - mechanics using this database must never treat such an
ID as a valid swap target or donor. This is enforced by
get_monster()/get_donor_data() below raising rather than silently
returning bad data.

MONSTERS: dict keyed by card_id (int). Every one of the 225 named
cards from cards.txt has an entry; most start with sound_id=None and
native_levels={} (i.e. "known to exist, not yet investigated") and get
filled in over time as more monsters get used as donors. Entries with
a card_id above MAX_NORMAL_CARD_ID (i.e. special entities) are
deliberately NOT included here at all - they were never in cards.txt
in the first place, since cards.txt itself only lists normal, ownable
cards.

    name: str
    sound_id: int or None - internal creature/sound ID (NOT the same
        as card_id) - used as the extraParam for the case 0x16/0x13
        sound-preload pair. None if not yet confirmed via direct
        e0XX.pps sub-table parsing for this specific card.
    native_levels: dict mapping a level file's own name (e.g.
        "s17.pds") to {"file_offset": int, "size": int} - the absolute
        file offset and byte size of this monster's own resource block
        within that level file's own monster table (found via
        header+0x14's own self-relative offset scheme - see any
        mechanic's own history for the full derivation). Empty dict if
        this card has never been used/confirmed as a donor from any
        level.

NATIVE_SLOTS: per-level-file dict mapping a level's own native monster
slot addresses (within the shared &DAT_80236358-based resource table)
to the card_id of whichever monster natively occupies that slot before
any swap. Populated for every level scanned by extract_monster_data.py
(49 levels as of this revision) using predicted_slot_addr =
0x80238e18 + table_index * 0x24, where table_index is that monster's
own 0-based position in its level file's own raw monster table (see
extract_monster_data.py's own "PREDICTED SLOT ADDRESSES" docstring
section for the full derivation).

IMPORTANT: only s01.pds's own Beaker (0x80238e18) and Dark Raven
(0x80238e3c) entries are directly confirmed via live testing. Every
other entry in this dict - including the rest of s01.pds's own slots -
is an ACCEPTED, UNVERIFIED prediction: the project owner has
explicitly chosen to proceed with these as-is rather than confirm each
one individually via live memory tracing first. If a specific level's
swap ever looks wrong in-game (wrong model/texture, or a crash),
this is the first place to check - that level's own predicted base
address/stride may not hold.
"""

MAX_NORMAL_CARD_ID = 0xe8  # confirmed via cards.txt's own highest entry (Sacred Umpire)

MONSTERS = {
    0x1: {"name": 'Skeleton', "sound_id": 0, "native_levels": {"s56.pds": {"file_offset": 0x20ce60, "size": 0x21c80, "textures": [(0x4e21, 0x1a4d80, 0xa820, False)]}}, "ctm_size": 0x2f2e0},
    0x2: {"name": 'Ghost Armor', "sound_id": 1, "native_levels": {"s60.pds": {"file_offset": 0x1f4560, "size": 0x2c4a0, "textures": [(0x4e22, 0x178d60, 0xa820, False)]}}, "ctm_size": 0x1e2e0},
    0x3: {"name": 'Red Dragon', "sound_id": 2, "native_levels": {"s27.pds": {"file_offset": 0x3109a0, "size": 0x2d060, "textures": [(0x4e23, 0x2529e0, 0x15520, False)]}, "s63.pds": {"file_offset": 0x1e77a0, "size": 0x2d060, "textures": [(0x4e23, 0x178d40, 0x15520, False)]}}, "ctm_size": 0x35680},
    0x4: {"name": 'Golden Goose', "sound_id": 3, "native_levels": {"s92.pds": {"file_offset": 0x1b32e0, "size": 0x1e820, "textures": [(0x4e24, 0x1ab2a0, 0x8020, False)]}}, "ctm_size": 0x26780},
    0x5: {"name": 'Lizardman', "sound_id": 12, "native_levels": {"s22.pds": {"file_offset": 0x251f20, "size": 0x43280, "textures": [(0x4e25, 0x1e06a0, 0xa820, False), (0x54, 0x21a340, 0xa820, True)]}, "s51.pds": {"file_offset": 0x1ba860, "size": 0x43280, "textures": [(0x4e25, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x184e0},
    0x6: {"name": 'Valkyrie', "sound_id": 202, "native_levels": {"s27.pds": {"file_offset": 0x2a5460, "size": 0x309e0, "textures": [(0x4e26, 0x22dd60, 0xa820, False), (0x501a, 0x238580, 0x5420, False)]}, "s53.pds": {"file_offset": 0x238da0, "size": 0x309e0, "textures": [(0x4e26, 0x19d9c0, 0xa820, False), (0x501a, 0x1a81e0, 0x5420, False)]}}, "ctm_size": 0x41f40},
    0x7: {"name": 'Thanatos', "sound_id": 190, "native_levels": {"s25.pds": {"file_offset": 0x278b40, "size": 0x2d140, "textures": [(0x4e27, 0x225ee0, 0xa820, False), (0x501b, 0x230700, 0x2a20, False)]}}, "ctm_size": 0x2cd80},
    0x8: {"name": 'Cerberus', "sound_id": 253, "native_levels": {"s27.pds": {"file_offset": 0x33da00, "size": 0x236a0, "textures": [(0x4e28, 0x267f00, 0xa820, False)]}}, "ctm_size": 0x4c5e0},
    0x9: {"name": 'Phoenix', "sound_id": 262, "native_levels": {"s27.pds": {"file_offset": 0x3610a0, "size": 0x35ca0, "textures": [(0x4e29, 0x272720, 0xa820, False)]}}, "ctm_size": 0x3cde0},
    0xa: {"name": 'Mandragora', "sound_id": 21, "native_levels": {"s04.pds": {"file_offset": 0x1e5580, "size": 0x10780, "textures": [(0x4e2a, 0x1c5260, 0xaa0, False)]}}, "ctm_size": 0x1e5e0},
    0xb: {"name": 'Red Lizard', "sound_id": 5, "native_levels": {"s51.pds": {"file_offset": 0x225b40, "size": 0x30e00, "textures": [(0x4e2b, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x1c080},
    0xc: {"name": 'Unicorn', "sound_id": 25, "native_levels": {}, "ctm_size": 0x4cae0},
    0xd: {"name": 'Hobgoblin', "sound_id": 6, "native_levels": {"s52.pds": {"file_offset": 0x1b7e40, "size": 0x23340, "textures": [(0x4e2d, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x33480},
    0xe: {"name": 'Centaur', "sound_id": 263, "native_levels": {}, "ctm_size": 0x5a7e0},
    0xf: {"name": 'Sand Golem', "sound_id": 14, "native_levels": {"s10.pds": {"file_offset": 0x2b0c80, "size": 0x1d220, "textures": [(0x4e2f, 0x237c80, 0xa820, False), (0x52, 0x22d460, 0xa820, True), (0x57, 0x261ce0, 0xa820, True)]}}, "ctm_size": 0x27840},
    0x10: {"name": 'Jack-O-Lantern', "sound_id": 69, "native_levels": {}, "ctm_size": 0x1fc00},
    0x11: {"name": 'Devil Plant', "sound_id": 233, "native_levels": {"s10.pds": {"file_offset": 0x2cdea0, "size": 0x269e0, "textures": [(0x4e31, 0x2424a0, 0xa820, False), (0x52, 0x22d460, 0xa820, True)]}}, "ctm_size": 0x31280},
    0x12: {"name": 'Man Trap', "sound_id": 19, "native_levels": {"s02.pds": {"file_offset": 0x2ec920, "size": 0x26860, "textures": [(0x4e32, 0x263820, 0xa820, False)]}}, "ctm_size": 0x310e0},
    0x13: {"name": 'Ashura', "sound_id": 264, "native_levels": {"s27.pds": {"file_offset": 0x2877a0, "size": 0x1dcc0, "textures": [(0x4e33, 0x21e120, 0xa820, False)]}, "s53.pds": {"file_offset": 0x269780, "size": 0x1dcc0, "textures": [(0x4e33, 0x1ad600, 0xa820, False)]}}, "ctm_size": 0x23ee0},
    0x14: {"name": 'Sand Worm', "sound_id": 26, "native_levels": {"s22.pds": {"file_offset": 0x2951a0, "size": 0x3afe0, "textures": [(0x4e34, 0x1eaec0, 0x15020, False), (0x54, 0x21a340, 0xa820, True)]}}, "ctm_size": 0x326a0},
    0x15: {"name": 'Mummy', "sound_id": 70, "native_levels": {"s22.pds": {"file_offset": 0x224ba0, "size": 0x2d380, "textures": [(0x4e35, 0x1d5920, 0xa820, False), (0x5029, 0x1e0140, 0x560, False)]}}, "ctm_size": 0x1b880},
    0x16: {"name": 'Cockatrice', "sound_id": 38, "native_levels": {"s07.pds": {"file_offset": 0x24c680, "size": 0x44ac0, "textures": [(0x4e36, 0x1d9f20, 0xa820, False), (0x3c, 0x1cf700, 0xa820, True)]}}, "ctm_size": 0x1b4e0},
    0x17: {"name": 'Sasquatch', "sound_id": 32, "native_levels": {"s25.pds": {"file_offset": 0x2a5c80, "size": 0x2df60, "textures": [(0x502b, 0x23d940, 0x5420, True), (0x4e37, 0x233120, 0xa820, False)]}}, "ctm_size": 0x2b180},
    0x18: {"name": 'Wraith', "sound_id": 33, "native_levels": {"s64.pds": {"file_offset": 0x22fd40, "size": 0x26940, "textures": [(0x4e38, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x15ca0},
    0x19: {"name": 'Orc', "sound_id": 22, "native_levels": {"s52.pds": {"file_offset": 0x2306a0, "size": 0x2e840, "textures": [(0x4e39, 0x1ad5e0, 0xa820, False)]}}, "ctm_size": 0x1a2a0},
    0x1a: {"name": 'Barometz', "sound_id": 204, "native_levels": {"s11.pds": {"file_offset": 0x2b0120, "size": 0x17240, "textures": [(0x4e3a, 0x213540, 0xa820, False)]}}, "ctm_size": 0x1bcc0},
    0x1b: {"name": 'Fairy', "sound_id": 27, "native_levels": {}, "ctm_size": 0x341c0},
    0x1c: {"name": 'Mind Flayer', "sound_id": 58, "native_levels": {"s66.pds": {"file_offset": 0x24c180, "size": 0x22100, "textures": [(0x4e3c, 0x1e3220, 0xa820, False), (0x5030, 0x1eda40, 0x2a20, False)]}}, "ctm_size": 0x35c60},
    0x1d: {"name": 'Succubus', "sound_id": 184, "native_levels": {"s01.pds": {"file_offset": 0x2b0a00, "size": 0x301e0, "textures": [(0x4e3d, 0x1fedc0, 0xa820, False), (0x55, 0x20ab00, 0xa820, True), (0x5031, 0x2095e0, 0x1520, False)]}}, "ctm_size": 0x30340},
    0x1e: {"name": 'Incubus', "sound_id": 185, "native_levels": {"s01.pds": {"file_offset": 0x27e740, "size": 0x322c0, "textures": [(0x4e3e, 0x1f45a0, 0xa820, False), (0x55, 0x20ab00, 0xa820, True)]}}, "ctm_size": 0x33340},
    0x1f: {"name": 'Catoblepas', "sound_id": 71, "native_levels": {"s17.pds": {"file_offset": 0x29cd80, "size": 0x14600, "textures": [(0x4e3f, 0x1fa8a0, 0xa820, False), (0x51, 0x234520, 0xa820, True)]}}, "ctm_size": 0x1ee80},
    0x20: {"name": 'Kraken', "sound_id": 72, "native_levels": {"s23.pds": {"file_offset": 0x28cfa0, "size": 0x2d060, "textures": [(0x4e40, 0x1e14e0, 0x15020, False)]}, "s40.pds": {"file_offset": 0x2a6500, "size": 0x910}, "s68.pds": {"file_offset": 0x2a7160, "size": 0x2d060, "textures": [(0x4e40, 0x1ed220, 0x15020, False)]}}, "ctm_size": 0x31920},
    0x21: {"name": 'Water Reaper', "sound_id": 59, "native_levels": {"s06.pds": {"file_offset": 0x27e5c0, "size": 0x220a0, "textures": [(0x4e41, 0x205aa0, 0xa820, False)]}}, "ctm_size": 0x128a0},
    0x22: {"name": 'Fenril', "sound_id": 73, "native_levels": {"s15.pds": {"file_offset": 0x253000, "size": 0x28de0, "textures": [(0x4e42, 0x1abf00, 0xa820, False), (0x4c, 0x1f5d40, 0x2a20, True), (0x4b, 0x1eb520, 0xa820, True), (0x5036, 0x1b6720, 0x560, False)]}, "s61.pds": {"file_offset": 0x1e01e0, "size": 0x28de0, "textures": [(0x4e42, 0x18dd80, 0xa820, False), (0x5036, 0x1985a0, 0x560, False)]}}, "ctm_size": 0x38320},
    0x23: {"name": 'Lich', "sound_id": 28, "native_levels": {"s23.pds": {"file_offset": 0x24fec0, "size": 0x3d0e0, "textures": [(0x4e43, 0x1d18a0, 0xa820, False), (0x5037, 0x1dc0c0, 0x5420, False), (0x53, 0x1f6500, 0xa820, True)]}}, "ctm_size": 0x211e0},
    0x24: {"name": 'Carbuncle', "sound_id": 15, "native_levels": {"s58.pds": {"file_offset": 0x1f4ea0, "size": 0x2e720, "textures": [(0x4e44, 0x18b3a0, 0xa820, False)]}}, "ctm_size": 0x19980},
    0x25: {"name": 'Chameleus', "sound_id": 199, "native_levels": {"s60.pds": {"file_offset": 0x245280, "size": 0x22a80, "textures": [(0x500d, 0x1b2a20, 0xa820, False)]}}, "ctm_size": 0x61ba0},
    0x26: {"name": 'Flayer Spawn', "sound_id": 42, "native_levels": {"s06.pds": {"file_offset": 0x242f60, "size": 0x3b660, "textures": [(0x4e46, 0x2003c0, 0x5420, False)]}}, "ctm_size": 0x16360},
    0x27: {"name": 'Elephant King', "sound_id": 7, "native_levels": {"s57.pds": {"file_offset": 0x202180, "size": 0x27200, "textures": [(0x4e47, 0x18dd80, 0x15020, False)]}}, "ctm_size": 0x4cc40},
    0x28: {"name": 'Zombie Dragon', "sound_id": 51, "native_levels": {"s17.pds": {"file_offset": 0x2cd2e0, "size": 0x1d1a0, "textures": [(0x4e48, 0x21a0e0, 0x15020, False), (0x503c, 0x22f100, 0x5420, False), (0x51, 0x234520, 0xa820, True)]}}, "ctm_size": 0x321a0},
    0x29: {"name": 'Fire Golem', "sound_id": 8, "native_levels": {"s52.pds": {"file_offset": 0x1f2300, "size": 0x15c40, "textures": [(0x4e49, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x20b80},
    0x2a: {"name": 'Running Bird', "sound_id": 31, "native_levels": {"s13.pds": {"file_offset": 0x1b2960, "size": 0x2f740, "textures": [(0x503e, 0x17e080, 0x5420, False), (0x5232, 0x1834a0, 0x2a20, False), (0x4e4a, 0x17b660, 0x2a20, False)]}, "s54.pds": {"file_offset": 0x1d6d80, "size": 0x2f740, "textures": [(0x503e, 0x180b80, 0x5420, False), (0x5232, 0x185fa0, 0x2a20, False), (0x4e4a, 0x17e160, 0x2a20, False)]}}, "ctm_size": 0x39f80},
    0x2b: {"name": 'Giant Crab', "sound_id": 39, "native_levels": {"s05.pds": {"file_offset": 0x19e700, "size": 0x1bfc0, "textures": [(0x4e4b, 0x14fa00, 0xa820, False)]}}, "ctm_size": 0x20640},
    0x2c: {"name": 'Banshee', "sound_id": 52, "native_levels": {"s56.pds": {"file_offset": 0x1f1ce0, "size": 0x1b180, "textures": [(0x4e4c, 0x1985a0, 0xa820, False), (0x5040, 0x1a2dc0, 0x1520, False), (0x5234, 0x1a42e0, 0xaa0, True)]}}, "ctm_size": 0x14920},
    0x2d: {"name": 'Land Shark', "sound_id": 40, "native_levels": {"s05.pds": {"file_offset": 0x1ba6c0, "size": 0x11f20, "textures": [(0x4e4d, 0x15a220, 0x5420, False)]}}, "ctm_size": 0x173a0},
    0x2e: {"name": 'Berserker', "sound_id": 43, "native_levels": {"s50.pds": {"file_offset": 0x209980, "size": 0x2ca20, "textures": [(0x4e4e, 0x18dd80, 0xa820, False), (0x5042, 0x1985a0, 0x2a20, False), (0x4ea6, 0x183560, 0xa820, True)]}}, "ctm_size": 0x39c80},
    0x2f: {"name": 'Flying Ray', "sound_id": 29, "native_levels": {"s50.pds": {"file_offset": 0x25e4e0, "size": 0x2ce20, "textures": [(0x4e4f, 0x1a6280, 0xa820, False), (0x524d, 0x1b88e0, 0x8020, False)]}}, "ctm_size": 0x18740},
    0x30: {"name": 'Demon Hound', "sound_id": 18, "native_levels": {"s07.pds": {"file_offset": 0x291140, "size": 0x36220, "textures": [(0x4e50, 0x1e4740, 0xa820, False), (0x5044, 0x1eef60, 0x1520, False)]}}, "ctm_size": 0x421e0},
    0x31: {"name": 'Behemoth', "sound_id": 41, "native_levels": {"s15.pds": {"file_offset": 0x27bde0, "size": 0x1a7e0, "textures": [(0x4e51, 0x1b6c80, 0x15020, False), (0x4b, 0x1eb520, 0xa820, True), (0x4c, 0x1f5d40, 0x2a20, True), (0x5045, 0x1cbca0, 0x5420, False)]}, "s57.pds": {"file_offset": 0x229380, "size": 0x1a7e0, "textures": [(0x4e51, 0x1a2da0, 0x15020, False), (0x5045, 0x1b7dc0, 0x5420, False)]}}, "ctm_size": 0x34f00},
    0x32: {"name": 'Mole Monster', "sound_id": 44, "native_levels": {"s54.pds": {"file_offset": 0x27de20, "size": 0x214a0, "textures": [(0x4e52, 0x1a8260, 0xa820, False)]}}, "ctm_size": 0x24140},
    0x33: {"name": 'Maelstrom', "sound_id": 45, "native_levels": {"s55.pds": {"file_offset": 0x261780, "size": 0x11940, "textures": [(0x4e53, 0x1c2600, 0x2a20, False)]}}, "ctm_size": 0x143a0},
    0x34: {"name": 'Garuda', "sound_id": 198, "native_levels": {"s61.pds": {"file_offset": 0x208fc0, "size": 0x1d7c0, "textures": [(0x4e54, 0x198b00, 0xa820, False)]}}, "ctm_size": 0x3aee0},
    0x35: {"name": 'Lycanthrope', "sound_id": 46, "native_levels": {"s59.pds": {"file_offset": 0x286e20, "size": 0x37480, "textures": [(0x4e55, 0x1a0ea0, 0xa820, False), (0x5049, 0x1ab6c0, 0x2a20, False)]}}, "ctm_size": 0x18e80},
    0x36: {"name": 'Sand Beetle', "sound_id": 47, "native_levels": {"s22.pds": {"file_offset": 0x3291c0, "size": 0x1c520, "textures": [(0x4e56, 0x20fb20, 0xa820, False)]}}, "ctm_size": 0x26d80},
    0x37: {"name": 'Necromancer', "sound_id": 11, "native_levels": {"s67.pds": {"file_offset": 0x23f660, "size": 0x26f00, "textures": [(0x4e57, 0x1d94a0, 0xa820, False), (0x504b, 0x1e3cc0, 0x2a20, False), (0x523f, 0x1e66e0, 0x1520, False)]}, "s95.pds": {"file_offset": 0x1d7b20, "size": 0x26ee0, "textures": [(0x4e57, 0x1c93a0, 0xa820, False), (0x504b, 0x1d3bc0, 0x2a20, False), (0x523f, 0x1d65e0, 0x1520, False)]}}, "ctm_size": 0x26980},
    0x38: {"name": 'Great Turtle', "sound_id": 53, "native_levels": {"s69.pds": {"file_offset": 0x302280, "size": 0x1e920, "textures": [(0x4e58, 0x219120, 0x15020, False)]}}, "ctm_size": 0x39760},
    0x39: {"name": 'Gold Butterfly', "sound_id": 16, "native_levels": {"s08.pds": {"file_offset": 0x2964c0, "size": 0x15d80, "textures": [(0x4e59, 0x21a500, 0x2a20, False), (0x504d, 0x21cf20, 0x2a20, False)]}, "s59.pds": {"file_offset": 0x1c3140, "size": 0x15d80, "textures": [(0x4e59, 0x178d40, 0x2a20, False), (0x504d, 0x17b760, 0x2a20, False)]}}, "ctm_size": 0x212a0},
    0x3a: {"name": 'Ghoul', "sound_id": 17, "native_levels": {"s60.pds": {"file_offset": 0x281da0, "size": 0x271c0, "textures": [(0x4e5a, 0x1dcaa0, 0xa820, False)]}}, "ctm_size": 0x17580},
    0x3b: {"name": 'Treant', "sound_id": 48, "native_levels": {"s51.pds": {"file_offset": 0x27f6a0, "size": 0x13760, "textures": [(0x4e5b, 0x1a2dc0, 0xa820, False)]}}, "ctm_size": 0x21920},
    0x3c: {"name": 'Nueh', "sound_id": 216, "native_levels": {"s23.pds": {"file_offset": 0x20b580, "size": 0x2aea0, "textures": [(0x4e5c, 0x1b2060, 0x15020, False), (0x57, 0x200d20, 0xa820, True), (0x53, 0x1f6500, 0xa820, True)]}, "s68.pds": {"file_offset": 0x27c2c0, "size": 0x2aea0, "textures": [(0x4e5c, 0x1d8200, 0x15020, False)]}}, "ctm_size": 0x31040},
    0x3d: {"name": 'Sea Monk', "sound_id": 74, "native_levels": {"s62.pds": {"file_offset": 0x1f71e0, "size": 0x17980, "textures": [(0x4e5d, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x33240},
    0x3e: {"name": 'Crystal Rose', "sound_id": 49, "native_levels": {"s05.pds": {"file_offset": 0x1cc5e0, "size": 0x28820, "textures": [(0x4e5e, 0x15f640, 0xa820, False)]}}, "ctm_size": 0x17a40},
    0x3f: {"name": 'Dark Raven', "sound_id": 9, "native_levels": {"s01.pds": {"file_offset": 0x232a60, "size": 0x12620, "textures": [(0x4e5f, 0x1dcb40, 0x2a20, False), (0x55, 0x20ab00, 0xa820, True)]}}, "ctm_size": 0x27de0},
    0x40: {"name": 'Black Dragon', "sound_id": 75, "native_levels": {"s13.pds": {"file_offset": 0x239e00, "size": 0x202e0, "textures": [(0x4e60, 0x19d920, 0x15020, False)]}, "s68.pds": {"file_offset": 0x2d41c0, "size": 0x202e0, "textures": [(0x4e60, 0x202240, 0x15020, False)]}}, "ctm_size": 0x35340},
    0x41: {"name": 'Wizard', "sound_id": 34, "native_levels": {"s51.pds": {"file_offset": 0x292e00, "size": 0x21ce0, "textures": [(0x4e61, 0x1ad5e0, 0xa820, False), (0x5055, 0x1b7e00, 0x2a20, False)]}}, "ctm_size": 0x294a0},
    0x42: {"name": 'Dragonoid', "sound_id": 76, "native_levels": {"s54.pds": {"file_offset": 0x2064c0, "size": 0x34f20, "textures": [(0x4e62, 0x1889c0, 0xa820, False)]}}, "ctm_size": 0x18b80},
    0x43: {"name": 'Dryad', "sound_id": 60, "native_levels": {"s07.pds": {"file_offset": 0x2c7360, "size": 0x19d80, "textures": [(0x4e63, 0x1f0480, 0xa820, False), (0x3c, 0x1cf700, 0xa820, True)]}, "s61.pds": {"file_offset": 0x1b83a0, "size": 0x19d80, "textures": [(0x4e63, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x2ac20},
    0x44: {"name": 'Birdman', "sound_id": 61, "native_levels": {"s21.pds": {"file_offset": 0x2cefa0, "size": 0x1c4c0, "textures": [(0x4e64, 0x2461e0, 0xa820, False)]}}, "ctm_size": 0x37840},
    0x45: {"name": "Will 'o wisp", "sound_id": 23, "native_levels": {"s50.pds": {"file_offset": 0x28b300, "size": 0x6820, "textures": [(0x4e65, 0x1b0aa0, 0x5420, False), (0x5059, 0x1b5ec0, 0x2a20, False)]}}, "ctm_size": 0x17860},
    0x46: {"name": 'Archer Tree', "sound_id": 62, "native_levels": {"s60.pds": {"file_offset": 0x220a00, "size": 0x24880, "textures": [(0x4e66, 0x183580, 0xa820, False), (0x505a, 0x18dda0, 0x5420, False)]}}, "ctm_size": 0x471e0},
    0x47: {"name": 'Stone Head', "sound_id": 24, "native_levels": {"s21.pds": {"file_offset": 0x2eb460, "size": 0xf560, "textures": [(0x4e67, 0x250a00, 0xa820, False)]}}, "ctm_size": 0x1d880},
    0x48: {"name": 'Blood Bush', "sound_id": 63, "native_levels": {"s59.pds": {"file_offset": 0x257b20, "size": 0x2f300, "textures": [(0x4e68, 0x196680, 0xa820, False)]}}, "ctm_size": 0x1b620},
    0x49: {"name": 'Efreet', "sound_id": 30, "native_levels": {"s27.pds": {"file_offset": 0x2ed140, "size": 0x23860, "textures": [(0x4e69, 0x2481c0, 0xa820, False)]}}, "ctm_size": 0x17320},
    0x4a: {"name": 'Dragon Knight', "sound_id": 77, "native_levels": {"s50.pds": {"file_offset": 0x1c0940, "size": 0x2d3e0, "textures": [(0x4e6a, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x17d60},
    0x4b: {"name": 'Demon Fox', "sound_id": 78, "native_levels": {"s15.pds": {"file_offset": 0x2965c0, "size": 0x530c0, "textures": [(0x4e6b, 0x1d10c0, 0xa820, False), (0x505f, 0x1db8e0, 0x5420, False), (0x4b, 0x1eb520, 0xa820, True), (0x4c, 0x1f5d40, 0x2a20, True)]}, "s53.pds": {"file_offset": 0x1e5ce0, "size": 0x530c0, "textures": [(0x4e6b, 0x18dd80, 0xa820, False), (0x505f, 0x1985a0, 0x5420, False)]}}, "ctm_size": 0x64500},
    0x4c: {"name": 'Juggernaut', "sound_id": 79, "native_levels": {"s20.pds": {"file_offset": 0x241a60, "size": 0x13d60, "textures": [(0x4e6c, 0x219c60, 0xa820, False), (0x56, 0x237220, 0xa820, True)]}, "s55.pds": {"file_offset": 0x212920, "size": 0x13d60, "textures": [(0x4e6c, 0x1985a0, 0xa820, False)]}}, "ctm_size": 0x11260},
    0x4d: {"name": 'Fire Gargoyle', "sound_id": 65, "native_levels": {"s27.pds": {"file_offset": 0x2d5e40, "size": 0x17300, "textures": [(0x4e6d, 0x23d9a0, 0xa820, False)]}}, "ctm_size": 0x1b100},
    0x4e: {"name": 'Great Demon', "sound_id": 80, "native_levels": {"s53.pds": {"file_offset": 0x287440, "size": 0x28640, "textures": [(0x4e6e, 0x1bd240, 0xa820, False)]}}, "ctm_size": 0x16e20},
    0x4f: {"name": 'Evil Eye', "sound_id": 64, "native_levels": {"s08.pds": {"file_offset": 0x274c20, "size": 0x218a0, "textures": [(0x4e6f, 0x2150e0, 0x5420, False)]}}, "ctm_size": 0x23da0},
    0x50: {"name": 'Blue Dragon', "sound_id": 85, "native_levels": {"s69.pds": {"file_offset": 0x279400, "size": 0x37c80, "textures": [(0x4e70, 0x1e0980, 0x15020, False), (0x5064, 0x1f59a0, 0x2a20, False)]}}, "ctm_size": 0x43160},
    0x51: {"name": 'Gnome', "sound_id": 86, "native_levels": {"s17.pds": {"file_offset": 0x23ed80, "size": 0x1dca0, "textures": [(0x4e71, 0x1d8620, 0xa820, False), (0x51, 0x234520, 0xa820, True)]}, "s57.pds": {"file_offset": 0x1e44e0, "size": 0x1dca0, "textures": [(0x4e71, 0x183560, 0xa820, False)]}}, "ctm_size": 0x38e20},
    0x52: {"name": 'Tiger Mage', "sound_id": 87, "native_levels": {"s62.pds": {"file_offset": 0x20eb60, "size": 0x4cea0, "textures": [(0x4e72, 0x1985a0, 0xa820, False), (0x5066, 0x1a2dc0, 0x2a20, False), (0x525a, 0x1a57e0, 0xaa0, False)]}}, "ctm_size": 0x5f760},
    0x53: {"name": 'Hydra', "sound_id": 88, "native_levels": {"s25.pds": {"file_offset": 0x3305c0, "size": 0x3e820, "textures": [(0x4e73, 0x2625c0, 0x15020, False), (0x5067, 0x2775e0, 0x1520, False)]}}, "ctm_size": 0x3f7a0},
    0x54: {"name": 'Siren', "sound_id": 89, "native_levels": {"s08.pds": {"file_offset": 0x23ed40, "size": 0x17560, "textures": [(0x4e74, 0x1f5340, 0xa820, False)]}}, "ctm_size": 0x20dc0},
    0x55: {"name": 'Chimera', "sound_id": 35, "native_levels": {"s08.pds": {"file_offset": 0x2562a0, "size": 0x1e980, "textures": [(0x4e75, 0x1ffb60, 0x15020, False)]}}, "ctm_size": 0x2f520},
    0x56: {"name": 'Rheebus', "sound_id": 90, "native_levels": {}, "ctm_size": 0x22f20},
    0x57: {"name": 'Scythe Beast', "sound_id": 91, "native_levels": {"s50.pds": {"file_offset": 0x2363a0, "size": 0x28140, "textures": [(0x4e77, 0x19afc0, 0xa820, False), (0x506b, 0x1a57e0, 0xaa0, False)]}}, "ctm_size": 0x161a0},
    0x58: {"name": 'Kitty Trap', "sound_id": 92, "native_levels": {"s21.pds": {"file_offset": 0x29f720, "size": 0x12680, "textures": [(0x4e78, 0x231180, 0x5420, False), (0x506c, 0x2365a0, 0x5420, False)]}}, "ctm_size": 0x1cf00},
    0x59: {"name": 'Night Mare', "sound_id": 93, "native_levels": {"s54.pds": {"file_offset": 0x23b3e0, "size": 0x24820, "textures": [(0x506d, 0x198600, 0x2a20, False), (0x4e79, 0x1931e0, 0x5420, False), (0x5261, 0x19b020, 0x2a20, False)]}}, "ctm_size": 0x2f100},
    0x5a: {"name": 'Golden Phoenix', "sound_id": 94, "native_levels": {"s69.pds": {"file_offset": 0x320ba0, "size": 0x22f00, "textures": [(0x4e7a, 0x22e140, 0xa820, False)]}}, "ctm_size": 0x3e640},
    0x5b: {"name": 'White Tiger', "sound_id": 95, "native_levels": {"s69.pds": {"file_offset": 0x2d2d20, "size": 0x2f560, "textures": [(0x4e7b, 0x202be0, 0x15020, False), (0x506f, 0x217c00, 0x1520, False)]}}, "ctm_size": 0x48320},
    0x5c: {"name": 'Venus Spider', "sound_id": 96, "native_levels": {"s55.pds": {"file_offset": 0x1e0e80, "size": 0x31aa0, "textures": [(0x4e7c, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x313e0},
    0x5d: {"name": 'Vampire', "sound_id": 97, "native_levels": {"s67.pds": {"file_offset": 0x212220, "size": 0x2d440, "textures": [(0x4e7d, 0x1ce1e0, 0xa820, False)]}}, "ctm_size": 0x237c0},
    0x5e: {"name": 'Sphinx', "sound_id": 98, "native_levels": {"s16.pds": {"file_offset": 0x26c400, "size": 0x1b2e0, "textures": [(0x4e7e, 0x1e0e60, 0x15020, False), (0x5072, 0x1f5e80, 0x560, False)]}, "s57.pds": {"file_offset": 0x268d20, "size": 0x1b2e0, "textures": [(0x4e7e, 0x1c7a00, 0x15020, False), (0x5072, 0x1dca20, 0x560, False)]}}, "ctm_size": 0x25ee0},
    0x5f: {"name": 'Puppet Master', "sound_id": 99, "native_levels": {"s20.pds": {"file_offset": 0x2557c0, "size": 0x57f40, "textures": [(0x4e7f, 0x224480, 0xa820, False), (0x56, 0x237220, 0xa820, True), (0x5073, 0x22eca0, 0x560, False)]}, "s67.pds": {"file_offset": 0x266560, "size": 0x57f40, "textures": [(0x4e7f, 0x1e7c00, 0xa820, False), (0x5073, 0x1f2420, 0x560, False)]}}, "ctm_size": 0x317e0},
    0x60: {"name": 'Plague Rat', "sound_id": 66, "native_levels": {"s60.pds": {"file_offset": 0x2a8f60, "size": 0x48760, "textures": [(0x4e80, 0x1e72c0, 0xa820, False), (0x5074, 0x1f1ae0, 0x1520, False), (0x5268, 0x1f3000, 0x1520, False)]}}, "ctm_size": 0x42c80},
    0x61: {"name": 'Undine', "sound_id": 100, "native_levels": {"s65.pds": {"file_offset": 0x1b7e40, "size": 0x13540, "textures": [(0x4e81, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x21400},
    0x62: {"name": 'Whip Worm', "sound_id": 67, "native_levels": {"s61.pds": {"file_offset": 0x23d800, "size": 0x19860, "textures": [(0x4e82, 0x1adb40, 0xa820, False)]}}, "ctm_size": 0x17400},
    0x63: {"name": 'Trickster', "sound_id": 101, "native_levels": {"s54.pds": {"file_offset": 0x25fc00, "size": 0x1e220, "textures": [(0x4e83, 0x19da40, 0xa820, False)]}}, "ctm_size": 0x28a80},
    0x64: {"name": 'Caterpoker', "sound_id": 102, "native_levels": {"s17.pds": {"file_offset": 0x282220, "size": 0x1ab60, "textures": [(0x4e84, 0x1ed660, 0xa820, False), (0x5078, 0x1f7e80, 0x2a20, False)]}, "s58.pds": {"file_offset": 0x1ae100, "size": 0x1ab60, "textures": [(0x4e84, 0x178d40, 0xa820, False), (0x5078, 0x183560, 0x2a20, False)]}}, "ctm_size": 0x27cc0},
    0x65: {"name": 'Beelzebub', "sound_id": 103, "native_levels": {"s15.pds": {"file_offset": 0x21a680, "size": 0x38980, "textures": [(0x4e85, 0x1a16c0, 0x5420, False), (0x5079, 0x1a6ae0, 0x5420, False), (0x4b, 0x1eb520, 0xa820, True), (0x4c, 0x1f5d40, 0x2a20, True)]}}, "ctm_size": 0x366a0},
    0x66: {"name": 'Ice Golem', "sound_id": 104, "native_levels": {"s15.pds": {"file_offset": 0x2e9680, "size": 0x1be00, "textures": [(0x4c, 0x1f5d40, 0x2a20, True), (0x4b, 0x1eb520, 0xa820, True), (0x4e86, 0x1e0d00, 0xa820, False)]}, "s65.pds": {"file_offset": 0x1d3d80, "size": 0x1be00, "textures": [(0x4e86, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x2b160},
    0x67: {"name": 'King Mandragora', "sound_id": 130, "native_levels": {"s61.pds": {"file_offset": 0x226780, "size": 0x17080, "textures": [(0x4e87, 0x1a3320, 0xa820, False)]}}, "ctm_size": 0x31100},
    0x68: {"name": 'Basilisk', "sound_id": 152, "native_levels": {"s51.pds": {"file_offset": 0x256940, "size": 0x28d60, "textures": [(0x4e88, 0x1985a0, 0xa820, False)]}}, "ctm_size": 0x18be0},
    0x69: {"name": 'Larval Fly', "sound_id": 153, "native_levels": {"s64.pds": {"file_offset": 0x274a40, "size": 0x34960, "textures": [(0x4e89, 0x1ad5e0, 0x5420, False), (0x507d, 0x1b2a00, 0x5420, False)]}}, "ctm_size": 0x365a0},
    0x6a: {"name": 'Mermaid', "sound_id": 194, "native_levels": {"s64.pds": {"file_offset": 0x25d4c0, "size": 0x17580, "textures": [(0x4e8a, 0x1a2dc0, 0xa820, False)]}}, "ctm_size": 0x24180},
    0x6b: {"name": 'Demon Skeleton', "sound_id": 131, "native_levels": {"s65.pds": {"file_offset": 0x1efb80, "size": 0x24a60, "textures": [(0x4e8b, 0x1985a0, 0xa820, False)]}}, "ctm_size": 0x31b00},
    0x6c: {"name": 'Vampire Bush', "sound_id": 154, "native_levels": {"s64.pds": {"file_offset": 0x2a93a0, "size": 0x2f160, "textures": [(0x4e8c, 0x1b7e20, 0xa820, False)]}}, "ctm_size": 0x3bd60},
    0x6d: {"name": 'Elephant', "sound_id": 155, "native_levels": {"s22.pds": {"file_offset": 0x2d0180, "size": 0x31a20, "textures": [(0x4e8d, 0x1ffee0, 0x5420, False), (0x54, 0x21a340, 0xa820, True)]}}, "ctm_size": 0x417e0},
    0x6e: {"name": 'Goblin Lord', "sound_id": 156, "native_levels": {"s58.pds": {"file_offset": 0x26e0e0, "size": 0x237a0, "textures": [(0x4e8e, 0x1a38a0, 0xa820, False)]}}, "ctm_size": 0x35c80},
    0x6f: {"name": 'Cyclops', "sound_id": 157, "native_levels": {"s54.pds": {"file_offset": 0x1b54e0, "size": 0x218a0, "textures": [(0x4e8f, 0x178d40, 0x5420, False)]}}, "ctm_size": 0x23d20},
    0x70: {"name": 'Steel Skeleton', "sound_id": 158, "native_levels": {"s21.pds": {"file_offset": 0x336ac0, "size": 0x21ce0, "textures": [(0x4e90, 0x265a40, 0xa820, False)]}, "s69.pds": {"file_offset": 0x2b1080, "size": 0x21ca0, "textures": [(0x4e90, 0x1f83c0, 0xa820, False)]}}, "ctm_size": 0x2f580},
    0x71: {"name": 'Chaos Knight', "sound_id": 159, "native_levels": {"s02.pds": {"file_offset": 0x313180, "size": 0x2c460, "textures": [(0x4e91, 0x26e040, 0xa820, False)]}, "s67.pds": {"file_offset": 0x2eee60, "size": 0x2c460, "textures": [(0x4e91, 0x2079c0, 0xa820, False)]}}, "ctm_size": 0x1e1e0},
    0x72: {"name": 'Decoy Pillar', "sound_id": 132, "native_levels": {}, "ctm_size": 0xe6c0},
    0x73: {"name": 'Doppelganger', "sound_id": 234, "native_levels": {}, "ctm_size": 0x76d40},
    0x74: {"name": 'Salamander', "sound_id": 191, "native_levels": {"s53.pds": {"file_offset": 0x1c7aa0, "size": 0x15b20, "textures": [(0x4e94, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x30980},
    0x75: {"name": 'Venom Lizard', "sound_id": 160, "native_levels": {"s51.pds": {"file_offset": 0x1fdae0, "size": 0x28060, "textures": [(0x4e95, 0x183560, 0xa820, False)]}}, "ctm_size": 0x1b8a0},
    0x76: {"name": 'God of Destruction', "sound_id": 115, "native_levels": {}, "ctm_size": 0x5d2a0},
    0x77: {"name": 'Earth Elemental', "sound_id": 165, "native_levels": {"s57.pds": {"file_offset": 0x1dcfc0, "size": 0x7520, "textures": [(0x4e97, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x13bc0},
    0x78: {"name": 'Water Elemental', "sound_id": 166, "native_levels": {"s25.pds": {"file_offset": 0x327bc0, "size": 0x8a00, "textures": [(0x4e98, 0x257da0, 0xa820, False)]}, "s65.pds": {"file_offset": 0x1cb380, "size": 0x8a00, "textures": [(0x4e98, 0x183560, 0xa820, False)]}}, "ctm_size": 0x14d40},
    0x79: {"name": 'Fire Elemental', "sound_id": 167, "native_levels": {"s27.pds": {"file_offset": 0x396d40, "size": 0x8720, "textures": [(0x4e99, 0x27cf40, 0xa820, False)]}, "s53.pds": {"file_offset": 0x1dd5c0, "size": 0x8720, "textures": [(0x4e99, 0x183560, 0xa820, False)]}}, "ctm_size": 0x14c20},
    0x7a: {"name": 'Wood Elemental', "sound_id": 168, "native_levels": {"s61.pds": {"file_offset": 0x1d2120, "size": 0xe0c0, "textures": [(0x4e9a, 0x183560, 0xa820, False)]}}, "ctm_size": 0x19700},
    0x7b: {"name": 'Fafnir', "sound_id": 173, "native_levels": {"s68.pds": {"file_offset": 0x3221c0, "size": 0x2e4a0, "textures": [(0x4e9b, 0x22c2a0, 0x15020, True)]}}, "ctm_size": 0x350e0},
    0x7c: {"name": 'Baby Dragon', "sound_id": 195, "native_levels": {"s17.pds": {"file_offset": 0x25ca20, "size": 0x25800, "textures": [(0x4e9c, 0x1e2e40, 0xa820, False), (0x51, 0x234520, 0xa820, True)]}, "s63.pds": {"file_offset": 0x26f720, "size": 0x25800, "textures": [(0x4e9c, 0x1c7ee0, 0xa820, False)]}}, "ctm_size": 0x33c60},
    0x7d: {"name": 'Elf', "sound_id": 133, "native_levels": {"s07.pds": {"file_offset": 0x2ffa60, "size": 0x3d960, "textures": [(0x4e9d, 0x2054c0, 0xa820, False), (0x3c, 0x1cf700, 0xa820, True)]}}, "ctm_size": 0x4ea00},
    0x7e: {"name": 'Elf Lord', "sound_id": 174, "native_levels": {"s59.pds": {"file_offset": 0x225d60, "size": 0x31dc0, "textures": [(0x4e9e, 0x18be60, 0xa820, False)]}}, "ctm_size": 0x400c0},
    0x7f: {"name": 'Beaker', "sound_id": 140, "native_levels": {"s01.pds": {"file_offset": 0x215360, "size": 0x1d700, "textures": [(0x4e9f, 0x1d2320, 0xa820, False)]}}, "ctm_size": 0x27f60},
    0x80: {"name": 'Yowie', "sound_id": 149, "native_levels": {"s06.pds": {"file_offset": 0x2a0660, "size": 0x243a0, "textures": [(0x4ea0, 0x2102c0, 0x5420, False)]}}, "ctm_size": 0x29800},
    0x81: {"name": 'Hell Hound', "sound_id": 135, "native_levels": {"s01.pds": {"file_offset": 0x245080, "size": 0x396c0, "textures": [(0x4ea1, 0x1df560, 0xa820, False), (0x55, 0x20ab00, 0xa820, True)]}}, "ctm_size": 0x4b1a0},
    0x82: {"name": 'Lamassu', "sound_id": 206, "native_levels": {}, "ctm_size": 0x2c620},
    0x83: {"name": 'Wyvern', "sound_id": 186, "native_levels": {"s16.pds": {"file_offset": 0x23ba40, "size": 0x1bb80, "textures": [(0x4ea3, 0x1cbe20, 0xa820, False)]}, "s67.pds": {"file_offset": 0x2be4a0, "size": 0x1bb80, "textures": [(0x4ea3, 0x1f2980, 0xa820, False)]}}, "ctm_size": 0x2b460},
    0x84: {"name": 'Rabandos', "sound_id": 187, "native_levels": {"s24.pds": {"file_offset": 0x224ac0, "size": 0x66f60, "textures": [(0x4ea4, 0x1c1b60, 0xa820, False), (0x32, 0x1de9e0, 0xa820, True), (0x34, 0x1ea720, 0x2a20, True), (0x33, 0x1e9200, 0x1520, True), (0x39, 0x1ed140, 0xa820, True), (0x5098, 0x1cc380, 0x5420, False), (0x4f, 0x1f8e80, 0xa820, True), (0x4b, 0x1d17a0, 0xa820, True), (0x4c, 0x1dbfc0, 0x2a20, True), (0x58, 0x1f7960, 0x1520, True)]}}, "ctm_size": 0x43e00},
    0x85: {"name": 'Baba Yaga', "sound_id": 239, "native_levels": {"s25.pds": {"file_offset": 0x2f9dc0, "size": 0x2de00, "textures": [(0x4ea5, 0x24d580, 0xa820, False), (0x502b, 0x23d940, 0x5420, True)]}}, "ctm_size": 0x39640},
    0x86: {"name": 'Berserk Master', "sound_id": 175, "native_levels": {"s50.pds": {"file_offset": 0x1edd20, "size": 0x1bc60, "textures": [(0x4ea6, 0x183560, 0xa820, True)]}}, "ctm_size": 0x26440},
    0x87: {"name": 'Acid Cloud', "sound_id": 205, "native_levels": {"s58.pds": {"file_offset": 0x2235c0, "size": 0x1e160, "textures": [(0x4ea7, 0x1985e0, 0xaa0, False)]}}, "ctm_size": 0x1ec40},
    0x88: {"name": 'Pixie', "sound_id": 137, "native_levels": {"s22.pds": {"file_offset": 0x301ba0, "size": 0x27620, "textures": [(0x4ea8, 0x205300, 0xa820, False), (0x54, 0x21a340, 0xa820, True)]}}, "ctm_size": 0x41bc0},
    0x89: {"name": 'Dao', "sound_id": 244, "native_levels": {"s57.pds": {"file_offset": 0x243b60, "size": 0x251c0, "textures": [(0x4ea9, 0x1bd1e0, 0xa820, False)]}}, "ctm_size": 0x183a0},
    0x8a: {"name": 'Manticore', "sound_id": 136, "native_levels": {"s10.pds": {"file_offset": 0x2f4880, "size": 0x33ec0, "textures": [(0x4eaa, 0x24ccc0, 0x15020, False), (0x52, 0x22d460, 0xa820, True), (0x57, 0x261ce0, 0xa820, True)]}}, "ctm_size": 0x31300},
    0x8b: {"name": 'Jade Giant', "sound_id": 189, "native_levels": {"s08.pds": {"file_offset": 0x21f960, "size": 0x1f3e0, "textures": [(0x4eab, 0x1e9600, 0xa820, False)]}}, "ctm_size": 0x20be0},
    0x8c: {"name": 'Dark Elf', "sound_id": 176, "native_levels": {"s21.pds": {"file_offset": 0x2fa9c0, "size": 0x3c100, "textures": [(0x4eac, 0x25b220, 0xa820, False)]}}, "ctm_size": 0x4b8e0},
    0x8d: {"name": 'Gorgon', "sound_id": 177, "native_levels": {"s13.pds": {"file_offset": 0x219ac0, "size": 0x20340, "textures": [(0x4ead, 0x193100, 0xa820, False)]}}, "ctm_size": 0x1f780},
    0x8e: {"name": 'Marid', "sound_id": 245, "native_levels": {"s65.pds": {"file_offset": 0x231940, "size": 0x22d80, "textures": [(0x4eae, 0x1ad5e0, 0xa820, False)]}}, "ctm_size": 0x17f80},
    0x8f: {"name": 'Emperor', "sound_id": 246, "native_levels": {"s69.pds": {"file_offset": 0x2389a0, "size": 0x40a60, "textures": [(0x4eaf, 0x1d3740, 0xa820, False), (0x50a3, 0x1ddf60, 0x2a20, False)]}}, "ctm_size": 0x2d900},
    0x90: {"name": 'Death', "sound_id": 139, "native_levels": {"s21.pds": {"file_offset": 0x2b1da0, "size": 0x1d200, "textures": [(0x4eb0, 0x23b9c0, 0xa820, False)]}}, "ctm_size": 0x13960},
    0x91: {"name": 'Devata', "sound_id": 178, "native_levels": {"s20.pds": {"file_offset": 0x2ad700, "size": 0x21360, "textures": [(0x4eb1, 0x22f200, 0x8020, False), (0x56, 0x237220, 0xa820, True)]}}, "ctm_size": 0x29100},
    0x92: {"name": 'Brine Dragon', "sound_id": 146, "native_levels": {"s05.pds": {"file_offset": 0x212600, "size": 0x24540, "textures": [(0x4eb2, 0x17ee80, 0x15020, False)]}, "s63.pds": {"file_offset": 0x214800, "size": 0x24540, "textures": [(0x4eb2, 0x18e260, 0x15020, False)]}}, "ctm_size": 0x34940},
    0x93: {"name": 'March Hare', "sound_id": 145, "native_levels": {"s62.pds": {"file_offset": 0x25ba00, "size": 0x2d120, "textures": [(0x4eb3, 0x1a6280, 0xa820, False)]}, "s93.pds": {"file_offset": 0x148ca0, "size": 0x2d0a0, "textures": [(0x4eb3, 0x13e460, 0xa820, False)]}}, "ctm_size": 0x2f5a0},
    0x94: {"name": 'Ryuhi', "sound_id": 240, "native_levels": {"s68.pds": {"file_offset": 0x2f44a0, "size": 0x2dd20, "textures": [(0x4eb4, 0x221a80, 0xa820, False), (0x4e9b, 0x22c2a0, 0x15020, True)]}}, "ctm_size": 0x43a00},
    0x95: {"name": 'Pazuzu', "sound_id": 265, "native_levels": {"s62.pds": {"file_offset": 0x2bc120, "size": 0x35ea0, "textures": [(0x4eb5, 0x1bb2c0, 0xa820, False), (0x50a9, 0x1c5ae0, 0x5420, False)]}, "s94.pds": {"file_offset": 0x121fc0, "size": 0x35e40, "textures": [(0x4eb5, 0x112360, 0xa820, False), (0x50a9, 0x11cb80, 0x5420, False)]}}, "ctm_size": 0x44620},
    0x96: {"name": 'Napalm Beast', "sound_id": 235, "native_levels": {}, "ctm_size": 0x19960},
    0x97: {"name": 'Green Dragon', "sound_id": 169, "native_levels": {"s63.pds": {"file_offset": 0x238d40, "size": 0x1aa80, "textures": [(0x50ab, 0x1adaa0, 0x5420, False), (0x4eb7, 0x1a3280, 0xa820, False)]}}, "ctm_size": 0x24e60},
    0x98: {"name": 'Blue Mold', "sound_id": 163, "native_levels": {"s56.pds": {"file_offset": 0x1c0a20, "size": 0xfe80, "textures": [(0x4eb8, 0x183560, 0xa820, False)]}}, "ctm_size": 0x1a6e0},
    0x99: {"name": 'Daidarapochi', "sound_id": 196, "native_levels": {}, "ctm_size": 0x24480},
    0x9a: {"name": 'Demon Swordsman', "sound_id": 150, "native_levels": {"s21.pds": {"file_offset": 0x2702a0, "size": 0x2f480, "textures": [(0x4eba, 0x226960, 0xa820, False)]}, "s90.pds": {"file_offset": 0x13b900, "size": 0x2f480, "textures": [(0x4eba, 0x1310c0, 0xa820, False)]}, "s91.pds": {"file_offset": 0x13b900, "size": 0x2f480, "textures": [(0x4eba, 0x1310c0, 0xa820, False)]}}, "ctm_size": 0x17a40},
    0x9b: {"name": 'Amber Dragon', "sound_id": 147, "native_levels": {"s17.pds": {"file_offset": 0x2b1380, "size": 0x1bf60, "textures": [(0x4ebb, 0x2050c0, 0x15020, False), (0x51, 0x234520, 0xa820, True)]}, "s63.pds": {"file_offset": 0x2537c0, "size": 0x1bf60, "textures": [(0x4ebb, 0x1b2ec0, 0x15020, False)]}}, "ctm_size": 0x2cb20},
    0x9c: {"name": 'Porcupig', "sound_id": 143, "native_levels": {"s02.pds": {"file_offset": 0x2788a0, "size": 0x19620, "textures": [(0x4ebc, 0x2397a0, 0xa820, False)]}}, "ctm_size": 0x23e80},
    0x9d: {"name": 'Golden Porcupig', "sound_id": 144, "native_levels": {"s66.pds": {"file_offset": 0x2a7ba0, "size": 0x1c0c0, "textures": [(0x4ebd, 0x2054a0, 0xa820, False)]}}, "ctm_size": 0x268e0},
    0x9e: {"name": 'Vouivre', "sound_id": 188, "native_levels": {"s56.pds": {"file_offset": 0x1d08a0, "size": 0x21440, "textures": [(0x4ebe, 0x18dd80, 0xa820, False)]}}, "ctm_size": 0x14d80},
    0x9f: {"name": 'Psycho Dice', "sound_id": 197, "native_levels": {}, "ctm_size": 0x36280},
    0xa0: {"name": 'Dark Treant', "sound_id": 170, "native_levels": {"s11.pds": {"file_offset": 0x254e60, "size": 0xd460, "textures": [(0x4ec0, 0x1f12c0, 0xa820, False)]}}, "ctm_size": 0x161e0},
    0xa1: {"name": 'Phooka', "sound_id": 171, "native_levels": {"s62.pds": {"file_offset": 0x1caf40, "size": 0x10b40, "textures": [(0x4ec1, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x1b3a0},
    0xa2: {"name": 'Gemini', "sound_id": 179, "native_levels": {"s23.pds": {"file_offset": 0x236420, "size": 0x19aa0, "textures": [(0x4ec2, 0x1c7080, 0xa820, False), (0x53, 0x1f6500, 0xa820, True), (0x57, 0x200d20, 0xa820, True)]}}, "ctm_size": 0x19fa0},
    0xa3: {"name": 'Coal Treant', "sound_id": 180, "native_levels": {"s09.pds": {"file_offset": 0x2c0d40, "size": 0x1b540, "textures": [(0x4ec3, 0x262680, 0xa820, False), (0x4f01, 0x26cea0, 0xa820, True)]}}, "ctm_size": 0x21fa0},
    0xa4: {"name": 'Matador', "sound_id": 161, "native_levels": {"s52.pds": {"file_offset": 0x1db180, "size": 0x17180, "textures": [(0x4ec4, 0x183560, 0xa820, False)]}}, "ctm_size": 0x219e0},
    0xa5: {"name": 'Sleeping Giant', "sound_id": 162, "native_levels": {"s59.pds": {"file_offset": 0x2be2a0, "size": 0x1a560, "textures": [(0x4ec5, 0x1ae0e0, 0x15020, False)]}}, "ctm_size": 0x29420},
    0xa6: {"name": 'Fireworks', "sound_id": 254, "native_levels": {}, "ctm_size": 0x1af60},
    0xa7: {"name": 'Storm Hagan', "sound_id": 138, "native_levels": {"s02.pds": {"file_offset": 0x2aa540, "size": 0x1d4a0, "textures": [(0x4ec7, 0x24e7e0, 0xa820, False)]}}, "ctm_size": 0x23b20},
    0xa8: {"name": 'Rock Hagan', "sound_id": 141, "native_levels": {"s65.pds": {"file_offset": 0x2145e0, "size": 0x1d360, "textures": [(0x4ec8, 0x1a2dc0, 0xa820, False)]}}, "ctm_size": 0x22c20},
    0xa9: {"name": 'Bum Hagan', "sound_id": 142, "native_levels": {"s55.pds": {"file_offset": 0x243e80, "size": 0x1d900, "textures": [(0x4ec9, 0x1b7de0, 0xa820, False)]}}, "ctm_size": 0x21b20},
    0xaa: {"name": 'Global Bust', "sound_id": 230, "native_levels": {"s55.pds": {"file_offset": 0x1c5060, "size": 0xb8a0, "textures": [(0x4eca, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x16100},
    0xab: {"name": 'Gravity Pillar', "sound_id": 181, "native_levels": {"s55.pds": {"file_offset": 0x1d0900, "size": 0x10580, "textures": [(0x4ecb, 0x183560, 0xa820, False)]}}, "ctm_size": 0x1bc20},
    0xac: {"name": 'Talos', "sound_id": 231, "native_levels": {}, "ctm_size": 0x343e0},
    0xad: {"name": 'Charadrius', "sound_id": 274, "native_levels": {}, "ctm_size": 0xb2c0},
    0xae: {"name": 'Crystal Magic', "sound_id": 200, "native_levels": {}, "ctm_size": 0x18d20},
    0xaf: {"name": 'Leprechaun', "sound_id": 182, "native_levels": {"s56.pds": {"file_offset": 0x22eae0, "size": 0x19a40, "textures": [(0x4ecf, 0x1af5a0, 0xa820, False), (0x5234, 0x1a42e0, 0xaa0, True)]}}, "ctm_size": 0x242a0},
    0xb0: {"name": 'Tumble Chick', "sound_id": 213, "native_levels": {"s54.pds": {"file_offset": 0x29f2c0, "size": 0x13740, "textures": [(0x4ed0, 0x1b2a80, 0x2a20, False)]}}, "ctm_size": 0x160a0},
    0xb1: {"name": 'Mad Reverser', "sound_id": 148, "native_levels": {"s58.pds": {"file_offset": 0x1c8c60, "size": 0x2c240, "textures": [(0x4ed1, 0x185f80, 0x5420, False)]}}, "ctm_size": 0x31680},
    0xb2: {"name": 'Myconid', "sound_id": 232, "native_levels": {"s07.pds": {"file_offset": 0x2e10e0, "size": 0x1e980, "textures": [(0x4ed2, 0x1faca0, 0xa820, False), (0x3c, 0x1cf700, 0xa820, True)]}}, "ctm_size": 0x291e0},
    0xb3: {"name": 'Sleipnir', "sound_id": 224, "native_levels": {}, "ctm_size": 0x32ee0},
    0xb4: {"name": 'Spartoi', "sound_id": 225, "native_levels": {}, "ctm_size": 0x13d80},
    0xb5: {"name": 'Lucky Lion', "sound_id": 207, "native_levels": {}, "ctm_size": 0x22780},
    0xb6: {"name": 'Vodianoi', "sound_id": 208, "native_levels": {"s25.pds": {"file_offset": 0x2d3be0, "size": 0x261e0, "textures": [(0x4ed6, 0x242d60, 0xa820, False)]}}, "ctm_size": 0x30a40},
    0xb7: {"name": 'Uroboros', "sound_id": 247, "native_levels": {}, "ctm_size": 0x1f8a0},
    0xb9: {"name": 'Demon Lord', "sound_id": 255, "native_levels": {"s68.pds": {"file_offset": 0x241300, "size": 0x3afc0, "textures": [(0x4ed9, 0x1ce1e0, 0xa020, False)]}}, "ctm_size": 0x1ca20},
    0xbc: {"name": 'Yin Yang', "sound_id": 269, "native_levels": {"s66.pds": {"file_offset": 0x23cf80, "size": 0xf200, "textures": [(0x4edc, 0x1d8a00, 0xa820, False)]}}, "ctm_size": 0x19a60},
    0xbd: {"name": 'Boom Monkey', "sound_id": 270, "native_levels": {"s66.pds": {"file_offset": 0x20fd00, "size": 0x2d280, "textures": [(0x4edd, 0x1ce1e0, 0xa820, False)]}}, "ctm_size": 0x37aa0},
    0xbe: {"name": 'Rubber Froggy', "sound_id": 203, "native_levels": {"s62.pds": {"file_offset": 0x1dba80, "size": 0x1b760, "textures": [(0x4ede, 0x183560, 0xa820, False)]}}, "ctm_size": 0x25f80},
    0xbf: {"name": 'Popgun Charlie', "sound_id": 172, "native_levels": {"s52.pds": {"file_offset": 0x207f40, "size": 0x21da0, "textures": [(0x4edf, 0x1985a0, 0xa820, False)]}}, "ctm_size": 0x2c660},
    0xc0: {"name": 'Ice Skeleton', "sound_id": 248, "native_levels": {}, "ctm_size": 0x263e0},
    0xc1: {"name": 'Raflesia', "sound_id": 256, "native_levels": {"s60.pds": {"file_offset": 0x267d00, "size": 0x1a0a0, "textures": [(0x4ee1, 0x1d2280, 0xa820, False)]}}, "ctm_size": 0x24900},
    0xc3: {"name": 'Sprite', "sound_id": 257, "native_levels": {}, "ctm_size": 0x20bc0},
    0xc4: {"name": 'Acid Dragon', "sound_id": 226, "native_levels": {"s16.pds": {"file_offset": 0x2575c0, "size": 0x14e40, "textures": [(0x4ee4, 0x1d6640, 0xa820, False)]}, "s63.pds": {"file_offset": 0x294f20, "size": 0x14e40, "textures": [(0x4ee4, 0x1d2700, 0xa820, False)]}, "s67.pds": {"file_offset": 0x2da020, "size": 0x14e40, "textures": [(0x4ee4, 0x1fd1a0, 0xa820, False)]}}, "ctm_size": 0x235e0},
    0xc5: {"name": 'Dark Sprite', "sound_id": 258, "native_levels": {}, "ctm_size": 0x20be0},
    0xc6: {"name": 'Super Pumper', "sound_id": 273, "native_levels": {"s66.pds": {"file_offset": 0x2a1880, "size": 0x6320, "textures": [(0x4ee6, 0x1fac80, 0xa820, False)]}}, "ctm_size": 0x11820},
    0xc7: {"name": 'Undead Knight', "sound_id": 249, "native_levels": {}, "ctm_size": 0x2c180},
    0xc8: {"name": 'Panther Mage', "sound_id": 268, "native_levels": {"s59.pds": {"file_offset": 0x1d8ec0, "size": 0x4cea0, "textures": [(0x4ee8, 0x17e180, 0xa820, False), (0x50dc, 0x1889a0, 0x2a20, False), (0x52d0, 0x18b3c0, 0xaa0, False)]}}, "ctm_size": 0x5f700},
    0xc9: {"name": 'Sekmet', "sound_id": 250, "native_levels": {}, "ctm_size": 0x1dfe0},
    0xca: {"name": 'Gargoyle', "sound_id": 259, "native_levels": {"s13.pds": {"file_offset": 0x1e20a0, "size": 0x19a00, "textures": [(0x4eea, 0x185ec0, 0xa820, False)]}}, "ctm_size": 0x24260},
    0xcc: {"name": 'Pegasus', "sound_id": 227, "native_levels": {}, "ctm_size": 0x25fe0},
    0xcd: {"name": 'Octobush', "sound_id": 271, "native_levels": {"s62.pds": {"file_offset": 0x288b20, "size": 0x33600, "textures": [(0x4eed, 0x1b0aa0, 0xa820, False)]}, "s66.pds": {"file_offset": 0x26e280, "size": 0x33600, "textures": [(0x4eed, 0x1f0460, 0xa820, False)]}}, "ctm_size": 0x34420},
    0xce: {"name": 'Mandra Dancer', "sound_id": 214, "native_levels": {"s07.pds": {"file_offset": 0x33d3c0, "size": 0x179c0, "textures": [(0x4eee, 0x20fce0, 0x2a20, False)]}}, "ctm_size": 0x23960},
    0xcf: {"name": 'Horus', "sound_id": 215, "native_levels": {"s13.pds": {"file_offset": 0x1fbaa0, "size": 0x1e020, "textures": [(0x4eef, 0x1906e0, 0x2a20, False)]}}, "ctm_size": 0x20a60},
    0xd1: {"name": 'Chariobot', "sound_id": 251, "native_levels": {"s11.pds": {"file_offset": 0x2c7360, "size": 0x1d820, "textures": [(0x4ef1, 0x21dd60, 0xa820, True)]}}, "ctm_size": 0x361c0},
    0xd2: {"name": 'Phantom Ship', "sound_id": 252, "native_levels": {}, "ctm_size": 0x345c0},
    0xd3: {"name": 'Witchlette', "sound_id": 260, "native_levels": {"s64.pds": {"file_offset": 0x1ffc40, "size": 0x30100, "textures": [(0x4ef3, 0x183560, 0xa820, False)]}}, "ctm_size": 0x3a960},
    0xd4: {"name": 'Apsaras', "sound_id": 272, "native_levels": {"s64.pds": {"file_offset": 0x1c2680, "size": 0x3d5c0, "textures": [(0x4ef4, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x47da0},
    0xd5: {"name": 'Circasaurus', "sound_id": 151, "native_levels": {"s58.pds": {"file_offset": 0x241720, "size": 0x2c9c0, "textures": [(0x4ef5, 0x199080, 0xa820, False)]}}, "ctm_size": 0x3c6e0},
    0xd6: {"name": 'Anarchy Owl', "sound_id": 261, "native_levels": {}, "ctm_size": 0x1e1a0},
    0xd7: {"name": 'Stone Golem', "sound_id": 164, "native_levels": {"s05.pds": {"file_offset": 0x1f4e00, "size": 0x1d800, "textures": [(0x4ef7, 0x169e60, 0x15020, False)]}, "s55.pds": {"file_offset": 0x226680, "size": 0x1d800, "textures": [(0x4ef7, 0x1a2dc0, 0x15020, False)]}}, "ctm_size": 0x37d60},
    0xd8: {"name": 'Fire Moray', "sound_id": 236, "native_levels": {"s52.pds": {"file_offset": 0x229ce0, "size": 0x69c0, "textures": [(0x4ef8, 0x1a2dc0, 0xa820, False)]}}, "ctm_size": 0x12680},
    0xd9: {"name": 'Water Moray', "sound_id": 237, "native_levels": {"s64.pds": {"file_offset": 0x256680, "size": 0x6e40, "textures": [(0x4ef9, 0x1985a0, 0xa820, False)]}}, "ctm_size": 0x10380},
    0xda: {"name": 'Earth Moray', "sound_id": 238, "native_levels": {"s56.pds": {"file_offset": 0x1b9e00, "size": 0x6c20, "textures": [(0x4efa, 0x178d40, 0xa820, False)]}}, "ctm_size": 0x10280},
    0xdb: {"name": 'Gizmolizer', "sound_id": 134, "native_levels": {"s11.pds": {"file_offset": 0x2622c0, "size": 0x29340, "textures": [(0x50ef, 0x206300, 0x2a20, False), (0x4efb, 0x1fbae0, 0xa820, False), (0x4ef1, 0x21dd60, 0xa820, True)]}}, "ctm_size": 0x2dd80},
    0xdd: {"name": 'UberBomberBot', "sound_id": 209, "native_levels": {"s05.pds": {"file_offset": 0x236b40, "size": 0xf7c0, "textures": [(0x4efd, 0x193ea0, 0xa820, False)]}}, "ctm_size": 0x1a020},
    0xde: {"name": 'Aggressor GL2', "sound_id": 210, "native_levels": {"s02.pds": {"file_offset": 0x291ec0, "size": 0x18680, "textures": [(0x4efe, 0x243fc0, 0xa820, False)]}, "s04.pds": {"file_offset": 0x1f5d00, "size": 0x18680, "textures": [(0x4efe, 0x1c5d00, 0xa820, False), (0x4f00, 0x1d0520, 0xa820, True)]}}, "ctm_size": 0x21820},
    0xdf: {"name": 'Super Scrubber', "sound_id": 211, "native_levels": {"s09.pds": {"file_offset": 0x2fe160, "size": 0x11680, "textures": [(0x4eff, 0x2776c0, 0xa820, False)]}}, "ctm_size": 0x19580},
    0xe0: {"name": 'MechaPult', "sound_id": 212, "native_levels": {"s04.pds": {"file_offset": 0x20e380, "size": 0x18ec0, "textures": [(0x4f00, 0x1d0520, 0xa820, True), (0x57, 0x1dad40, 0xa820, False)]}}, "ctm_size": 0x23720},
    0xe1: {"name": 'Aggressor DX5', "sound_id": 219, "native_levels": {"s09.pds": {"file_offset": 0x2dc280, "size": 0x21ee0, "textures": [(0x4f01, 0x26cea0, 0xa820, True)]}, "s15.pds": {"file_offset": 0x1f87a0, "size": 0x21ee0, "textures": [(0x4f01, 0x196ea0, 0xa820, False), (0x4c, 0x1f5d40, 0x2a20, True), (0x4b, 0x1eb520, 0xa820, True)]}, "s18.pds": {"file_offset": 0x22d480, "size": 0x21ee0, "textures": [(0x4f01, 0x1e3de0, 0xa820, False)]}}, "ctm_size": 0x2b080},
    0xe2: {"name": 'MechLance 5L', "sound_id": 220, "native_levels": {"s11.pds": {"file_offset": 0x22e3c0, "size": 0x26aa0, "textures": [(0x4f02, 0x1e6aa0, 0xa820, False)]}}, "ctm_size": 0x303a0},
    0xe3: {"name": 'Claws-R-Us', "sound_id": 221, "native_levels": {"s11.pds": {"file_offset": 0x28b600, "size": 0x24b20, "textures": [(0x4f03, 0x208d20, 0xa820, False)]}}, "ctm_size": 0x2d740},
    0xe4: {"name": 'TriBlaster', "sound_id": 222, "native_levels": {"s09.pds": {"file_offset": 0x281f00, "size": 0x1c4c0, "textures": [(0x4f04, 0x24d640, 0xa820, False)]}, "s18.pds": {"file_offset": 0x210fc0, "size": 0x1c4c0, "textures": [(0x4f04, 0x1d95c0, 0xa820, False)]}}, "ctm_size": 0x1ff40},
    0xe5: {"name": 'LazerBug 39K', "sound_id": 223, "native_levels": {"s09.pds": {"file_offset": 0x29e3c0, "size": 0x22980, "textures": [(0x4f05, 0x257e60, 0xa820, False)]}, "s18.pds": {"file_offset": 0x1ee640, "size": 0x22980, "textures": [(0x4f05, 0x1ceda0, 0xa820, False)]}}, "ctm_size": 0x25200},
    0xe6: {"name": 'AstroBot', "sound_id": 228, "native_levels": {"s24.pds": {"file_offset": 0x2036e0, "size": 0x213e0, "textures": [(0x4f06, 0x1b7340, 0xa820, False), (0x33, 0x1e9200, 0x1520, True), (0x39, 0x1ed140, 0xa820, True), (0x32, 0x1de9e0, 0xa820, True), (0x34, 0x1ea720, 0x2a20, True), (0x4b, 0x1d17a0, 0xa820, True), (0x58, 0x1f7960, 0x1520, True), (0x4f, 0x1f8e80, 0xa820, True), (0x4c, 0x1dbfc0, 0x2a20, True)]}}, "ctm_size": 0x1a2e0},
    0xe7: {"name": 'AcidBot', "sound_id": 229, "native_levels": {"s11.pds": {"file_offset": 0x2285c0, "size": 0x5e00, "textures": [(0x4f07, 0x1e4080, 0x2a20, False)]}}, "ctm_size": 0x8860},
    0xe8: {"name": 'Sacred Umpire', "sound_id": 201, "native_levels": {}, "ctm_size": 0x2b7c0},
}

NATIVE_SLOTS = {
    "s01.pds": {
        0x80238e18: 0x7f,  # directly confirmed
        0x80238e3c: 0x3f,  # directly confirmed
        0x80238e60: 0x81,  # PREDICTED, unverified
        0x80238e84: 0x1e,  # PREDICTED, unverified
        0x80238ea8: 0x1d,  # PREDICTED, unverified
    },
    "s02.pds": {
        0x80238e18: 0x9c,  # PREDICTED, unverified
        0x80238e3c: 0xde,  # PREDICTED, unverified
        0x80238e60: 0xa7,  # PREDICTED, unverified
        0x80238ea8: 0x12,  # PREDICTED, unverified
        0x80238ecc: 0x71,  # PREDICTED, unverified
    },
    "s04.pds": {
        0x80238e18: 0xa,  # PREDICTED, unverified
        0x80238e3c: 0xde,  # PREDICTED, unverified
        0x80238e60: 0xe0,  # PREDICTED, unverified
    },
    "s05.pds": {
        0x80238e18: 0x2b,  # PREDICTED, unverified
        0x80238e3c: 0x2d,  # PREDICTED, unverified
        0x80238e60: 0x3e,  # PREDICTED, unverified
        0x80238e84: 0xd7,  # PREDICTED, unverified
        0x80238ea8: 0x92,  # PREDICTED, unverified
        0x80238ecc: 0xdd,  # PREDICTED, unverified
    },
    "s06.pds": {
        0x80238e3c: 0x26,  # PREDICTED, unverified
        0x80238e60: 0x21,  # PREDICTED, unverified
        0x80238e84: 0x80,  # PREDICTED, unverified
    },
    "s07.pds": {
        0x80238e3c: 0x16,  # PREDICTED, unverified
        0x80238e60: 0x30,  # PREDICTED, unverified
        0x80238e84: 0x43,  # PREDICTED, unverified
        0x80238ea8: 0xb2,  # PREDICTED, unverified
        0x80238ecc: 0x7d,  # PREDICTED, unverified
        0x80238ef0: 0xce,  # PREDICTED, unverified
    },
    "s08.pds": {
        0x80238e18: 0x8b,  # PREDICTED, unverified
        0x80238e3c: 0x54,  # PREDICTED, unverified
        0x80238e60: 0x55,  # PREDICTED, unverified
        0x80238e84: 0x4f,  # PREDICTED, unverified
        0x80238ea8: 0x39,  # PREDICTED, unverified
    },
    "s09.pds": {
        0x80238e18: 0xe4,  # PREDICTED, unverified
        0x80238e3c: 0xe5,  # PREDICTED, unverified
        0x80238e60: 0xa3,  # PREDICTED, unverified
        0x80238e84: 0xe1,  # PREDICTED, unverified
        0x80238ea8: 0xdf,  # PREDICTED, unverified
    },
    "s10.pds": {
        0x80238e3c: 0xf,  # PREDICTED, unverified
        0x80238e60: 0x11,  # PREDICTED, unverified
        0x80238e84: 0x8a,  # PREDICTED, unverified
    },
    "s11.pds": {
        0x80238e18: 0xe7,  # PREDICTED, unverified
        0x80238e3c: 0xe2,  # PREDICTED, unverified
        0x80238e60: 0xa0,  # PREDICTED, unverified
        0x80238e84: 0xdb,  # PREDICTED, unverified
        0x80238ea8: 0xe3,  # PREDICTED, unverified
        0x80238ecc: 0x1a,  # PREDICTED, unverified
        0x80238ef0: 0xd1,  # PREDICTED, unverified
    },
    "s13.pds": {
        0x80238e18: 0x2a,  # PREDICTED, unverified
        0x80238e3c: 0xca,  # PREDICTED, unverified
        0x80238e60: 0xcf,  # PREDICTED, unverified
        0x80238e84: 0x8d,  # PREDICTED, unverified
        0x80238ea8: 0x40,  # PREDICTED, unverified
    },
    "s15.pds": {
        0x80238e18: 0xe1,  # PREDICTED, unverified
        0x80238e3c: 0x65,  # PREDICTED, unverified
        0x80238e60: 0x22,  # PREDICTED, unverified
        0x80238e84: 0x31,  # PREDICTED, unverified
        0x80238ea8: 0x4b,  # PREDICTED, unverified
        0x80238ecc: 0x66,  # PREDICTED, unverified
    },
    "s16.pds": {
        0x80238e60: 0x83,  # PREDICTED, unverified
        0x80238e84: 0xc4,  # PREDICTED, unverified
        0x80238ea8: 0x5e,  # PREDICTED, unverified
    },
    "s17.pds": {
        0x80238e18: 0x51,  # PREDICTED, unverified
        0x80238e3c: 0x7c,  # PREDICTED, unverified
        0x80238e60: 0x64,  # PREDICTED, unverified
        0x80238e84: 0x1f,  # PREDICTED, unverified
        0x80238ea8: 0x9b,  # PREDICTED, unverified
        0x80238ecc: 0x28,  # PREDICTED, unverified
    },
    "s18.pds": {
        0x80238e18: 0xe5,  # PREDICTED, unverified
        0x80238e3c: 0xe4,  # PREDICTED, unverified
        0x80238e60: 0xe1,  # PREDICTED, unverified
    },
    "s20.pds": {
        0x80238e18: 0x4c,  # PREDICTED, unverified
        0x80238e3c: 0x5f,  # PREDICTED, unverified
        0x80238e60: 0x91,  # PREDICTED, unverified
    },
    "s21.pds": {
        0x80238e18: 0x9a,  # PREDICTED, unverified
        0x80238e3c: 0x58,  # PREDICTED, unverified
        0x80238e60: 0x90,  # PREDICTED, unverified
        0x80238e84: 0x44,  # PREDICTED, unverified
        0x80238ea8: 0x47,  # PREDICTED, unverified
        0x80238ecc: 0x8c,  # PREDICTED, unverified
        0x80238ef0: 0x70,  # PREDICTED, unverified
    },
    "s22.pds": {
        0x80238e18: 0x15,  # PREDICTED, unverified
        0x80238e3c: 0x5,  # PREDICTED, unverified
        0x80238e60: 0x14,  # PREDICTED, unverified
        0x80238e84: 0x6d,  # PREDICTED, unverified
        0x80238ea8: 0x88,  # PREDICTED, unverified
        0x80238ecc: 0x36,  # PREDICTED, unverified
    },
    "s23.pds": {
        0x80238e18: 0x3c,  # PREDICTED, unverified
        0x80238e3c: 0xa2,  # PREDICTED, unverified
        0x80238e60: 0x23,  # PREDICTED, unverified
        0x80238e84: 0x20,  # PREDICTED, unverified
    },
    "s24.pds": {
        0x80238e18: 0xe6,  # PREDICTED, unverified
        0x80238e3c: 0x84,  # PREDICTED, unverified
    },
    "s25.pds": {
        0x80238e18: 0x7,  # PREDICTED, unverified
        0x80238e3c: 0x17,  # PREDICTED, unverified
        0x80238e60: 0xb6,  # PREDICTED, unverified
        0x80238e84: 0x85,  # PREDICTED, unverified
        0x80238ea8: 0x78,  # PREDICTED, unverified
        0x80238ecc: 0x53,  # PREDICTED, unverified
    },
    "s27.pds": {
        0x80238e18: 0x13,  # PREDICTED, unverified
        0x80238e3c: 0x6,  # PREDICTED, unverified
        0x80238e60: 0x4d,  # PREDICTED, unverified
        0x80238e84: 0x49,  # PREDICTED, unverified
        0x80238ea8: 0x3,  # PREDICTED, unverified
        0x80238ecc: 0x8,  # PREDICTED, unverified
        0x80238ef0: 0x9,  # PREDICTED, unverified
        0x80238f14: 0x79,  # PREDICTED, unverified
    },
    "s40.pds": {
        0x80238f38: 0x20,  # PREDICTED, unverified
        0x80238f5c: 0x2,  # PREDICTED, unverified
    },
    "s50.pds": {
        0x80238e18: 0x4a,  # PREDICTED, unverified
        0x80238e3c: 0x86,  # PREDICTED, unverified
        0x80238e60: 0x2e,  # PREDICTED, unverified
        0x80238e84: 0x57,  # PREDICTED, unverified
        0x80238ea8: 0x2f,  # PREDICTED, unverified
        0x80238ecc: 0x45,  # PREDICTED, unverified
    },
    "s51.pds": {
        0x80238e18: 0x5,  # PREDICTED, unverified
        0x80238e3c: 0x75,  # PREDICTED, unverified
        0x80238e60: 0xb,  # PREDICTED, unverified
        0x80238e84: 0x68,  # PREDICTED, unverified
        0x80238ea8: 0x3b,  # PREDICTED, unverified
        0x80238ecc: 0x41,  # PREDICTED, unverified
    },
    "s52.pds": {
        0x80238e18: 0xd,  # PREDICTED, unverified
        0x80238e3c: 0xa4,  # PREDICTED, unverified
        0x80238e60: 0x29,  # PREDICTED, unverified
        0x80238e84: 0xbf,  # PREDICTED, unverified
        0x80238ea8: 0xd8,  # PREDICTED, unverified
        0x80238ecc: 0x19,  # PREDICTED, unverified
    },
    "s53.pds": {
        0x80238e18: 0x74,  # PREDICTED, unverified
        0x80238e3c: 0x79,  # PREDICTED, unverified
        0x80238e60: 0x4b,  # PREDICTED, unverified
        0x80238e84: 0x6,  # PREDICTED, unverified
        0x80238ea8: 0x13,  # PREDICTED, unverified
        0x80238ecc: 0x4e,  # PREDICTED, unverified
    },
    "s54.pds": {
        0x80238e18: 0x6f,  # PREDICTED, unverified
        0x80238e3c: 0x2a,  # PREDICTED, unverified
        0x80238e60: 0x42,  # PREDICTED, unverified
        0x80238e84: 0x59,  # PREDICTED, unverified
        0x80238ea8: 0x63,  # PREDICTED, unverified
        0x80238ecc: 0x32,  # PREDICTED, unverified
        0x80238ef0: 0xb0,  # PREDICTED, unverified
    },
    "s55.pds": {
        0x80238e18: 0xaa,  # PREDICTED, unverified
        0x80238e3c: 0xab,  # PREDICTED, unverified
        0x80238e60: 0x5c,  # PREDICTED, unverified
        0x80238e84: 0x4c,  # PREDICTED, unverified
        0x80238ea8: 0xd7,  # PREDICTED, unverified
        0x80238ecc: 0xa9,  # PREDICTED, unverified
        0x80238ef0: 0x33,  # PREDICTED, unverified
    },
    "s56.pds": {
        0x80238e18: 0xda,  # PREDICTED, unverified
        0x80238e3c: 0x98,  # PREDICTED, unverified
        0x80238e60: 0x9e,  # PREDICTED, unverified
        0x80238e84: 0x2c,  # PREDICTED, unverified
        0x80238ea8: 0x1,  # PREDICTED, unverified
        0x80238ecc: 0xaf,  # PREDICTED, unverified
    },
    "s57.pds": {
        0x80238e18: 0x77,  # PREDICTED, unverified
        0x80238e3c: 0x51,  # PREDICTED, unverified
        0x80238e60: 0x27,  # PREDICTED, unverified
        0x80238e84: 0x31,  # PREDICTED, unverified
        0x80238ea8: 0x89,  # PREDICTED, unverified
        0x80238ecc: 0x5e,  # PREDICTED, unverified
    },
    "s58.pds": {
        0x80238e18: 0x64,  # PREDICTED, unverified
        0x80238e3c: 0xb1,  # PREDICTED, unverified
        0x80238e60: 0x24,  # PREDICTED, unverified
        0x80238e84: 0x87,  # PREDICTED, unverified
        0x80238ea8: 0xd5,  # PREDICTED, unverified
        0x80238ecc: 0x6e,  # PREDICTED, unverified
    },
    "s59.pds": {
        0x80238e18: 0x39,  # PREDICTED, unverified
        0x80238e3c: 0xc8,  # PREDICTED, unverified
        0x80238e60: 0x7e,  # PREDICTED, unverified
        0x80238e84: 0x48,  # PREDICTED, unverified
        0x80238ea8: 0x35,  # PREDICTED, unverified
        0x80238ecc: 0xa5,  # PREDICTED, unverified
    },
    "s60.pds": {
        0x80238e18: 0x2,  # PREDICTED, unverified
        0x80238e3c: 0x46,  # PREDICTED, unverified
        0x80238e60: 0x25,  # PREDICTED, unverified
        0x80238e84: 0xc1,  # PREDICTED, unverified
        0x80238ea8: 0x3a,  # PREDICTED, unverified
        0x80238ecc: 0x60,  # PREDICTED, unverified
    },
    "s61.pds": {
        0x80238e18: 0x43,  # PREDICTED, unverified
        0x80238e3c: 0x7a,  # PREDICTED, unverified
        0x80238e60: 0x22,  # PREDICTED, unverified
        0x80238e84: 0x34,  # PREDICTED, unverified
        0x80238ea8: 0x67,  # PREDICTED, unverified
        0x80238ecc: 0x62,  # PREDICTED, unverified
    },
    "s62.pds": {
        0x80238e18: 0xa1,  # PREDICTED, unverified
        0x80238e3c: 0xbe,  # PREDICTED, unverified
        0x80238e60: 0x3d,  # PREDICTED, unverified
        0x80238e84: 0x52,  # PREDICTED, unverified
        0x80238ea8: 0x93,  # PREDICTED, unverified
        0x80238ecc: 0xcd,  # PREDICTED, unverified
        0x80238ef0: 0x95,  # PREDICTED, unverified
    },
    "s63.pds": {
        0x80238e18: 0x3,  # PREDICTED, unverified
        0x80238e3c: 0x92,  # PREDICTED, unverified
        0x80238e60: 0x97,  # PREDICTED, unverified
        0x80238e84: 0x9b,  # PREDICTED, unverified
        0x80238ea8: 0x7c,  # PREDICTED, unverified
        0x80238ecc: 0xc4,  # PREDICTED, unverified
    },
    "s64.pds": {
        0x80238e18: 0xd4,  # PREDICTED, unverified
        0x80238e3c: 0xd3,  # PREDICTED, unverified
        0x80238e60: 0x18,  # PREDICTED, unverified
        0x80238e84: 0xd9,  # PREDICTED, unverified
        0x80238ea8: 0x6a,  # PREDICTED, unverified
        0x80238ecc: 0x69,  # PREDICTED, unverified
        0x80238ef0: 0x6c,  # PREDICTED, unverified
    },
    "s65.pds": {
        0x80238e18: 0x61,  # PREDICTED, unverified
        0x80238e3c: 0x78,  # PREDICTED, unverified
        0x80238e60: 0x66,  # PREDICTED, unverified
        0x80238e84: 0x6b,  # PREDICTED, unverified
        0x80238ea8: 0xa8,  # PREDICTED, unverified
        0x80238ecc: 0x8e,  # PREDICTED, unverified
    },
    "s66.pds": {
        0x80238e18: 0xbd,  # PREDICTED, unverified
        0x80238e3c: 0xbc,  # PREDICTED, unverified
        0x80238e60: 0x1c,  # PREDICTED, unverified
        0x80238e84: 0xcd,  # PREDICTED, unverified
        0x80238ea8: 0xc6,  # PREDICTED, unverified
        0x80238ecc: 0x9d,  # PREDICTED, unverified
    },
    "s67.pds": {
        0x80238e18: 0x5d,  # PREDICTED, unverified
        0x80238e3c: 0x37,  # PREDICTED, unverified
        0x80238e60: 0x5f,  # PREDICTED, unverified
        0x80238e84: 0x83,  # PREDICTED, unverified
        0x80238ea8: 0xc4,  # PREDICTED, unverified
        0x80238ecc: 0x71,  # PREDICTED, unverified
    },
    "s68.pds": {
        0x80238e18: 0xb9,  # PREDICTED, unverified
        0x80238e3c: 0x3c,  # PREDICTED, unverified
        0x80238e60: 0x20,  # PREDICTED, unverified
        0x80238e84: 0x40,  # PREDICTED, unverified
        0x80238ea8: 0x94,  # PREDICTED, unverified
        0x80238ecc: 0x7b,  # PREDICTED, unverified
    },
    "s69.pds": {
        0x80238e18: 0x8f,  # PREDICTED, unverified
        0x80238e3c: 0x50,  # PREDICTED, unverified
        0x80238e60: 0x70,  # PREDICTED, unverified
        0x80238e84: 0x5b,  # PREDICTED, unverified
        0x80238ea8: 0x38,  # PREDICTED, unverified
        0x80238ecc: 0x5a,  # PREDICTED, unverified
    },
    "s90.pds": {
        0x80238e18: 0x9a,  # PREDICTED, unverified
    },
    "s91.pds": {
        0x80238e18: 0x9a,  # PREDICTED, unverified
    },
    "s92.pds": {
        0x80238e18: 0x4,  # PREDICTED, unverified
    },
    "s93.pds": {
        0x80238e18: 0x93,  # PREDICTED, unverified
    },
    "s94.pds": {
        0x80238e18: 0x95,  # PREDICTED, unverified
    },
    "s95.pds": {
        0x80238e18: 0x37,  # PREDICTED, unverified
    },
}


def get_monster(card_id):
    """Look up a monster's own database entry by card ID, raising if it's
    a "special" (non-ownable) entity above MAX_NORMAL_CARD_ID - mechanics
    should never treat such an ID as a valid swap target or donor."""
    if card_id > MAX_NORMAL_CARD_ID:
        raise ValueError(
            f"card_id {hex(card_id)} exceeds MAX_NORMAL_CARD_ID ({hex(MAX_NORMAL_CARD_ID)}) "
            f"- this is a 'special' entity (e.g. the Stranger), never a valid swap target or donor."
        )
    if card_id not in MONSTERS:
        raise KeyError(f"card_id {hex(card_id)} not found in MONSTERS - not a known, named card.")
    return MONSTERS[card_id]


def get_donor_data(card_id, level_file):
    """Look up a monster's own donor data (file_offset, size, sound_id)
    for a specific level file, raising clearly if any piece is missing
    (i.e. this card hasn't been confirmed as a usable donor from that
    level yet) rather than silently returning None/incomplete data."""
    monster = get_monster(card_id)
    if level_file not in monster["native_levels"]:
        raise KeyError(
            f"{monster['name']} ({hex(card_id)}) has no confirmed native_levels entry "
            f"for {level_file!r} - not yet investigated as a donor from this level."
        )
    if monster["sound_id"] is None:
        raise ValueError(
            f"{monster['name']} ({hex(card_id)}) has no confirmed sound_id yet - "
            f"parse its own e0{card_id:02d}.pps file's sub-table 2 to find it "
            f"(see any existing mechanic's own history for the exact method)."
        )
    data = monster["native_levels"][level_file]
    return {
        "card_id": card_id,
        "name": monster["name"],
        "file_offset": data["file_offset"],
        "size": data["size"],
        "sound_id": monster["sound_id"],
        # Every GTX1 texture this monster uses, as
        # (texture_id, file_offset, size, shared) - a monster uses up to 12,
        # not one. `shared` means another monster in the same level uses the
        # same texture, so it must not be overwritten in place.
        # Absent only for entries whose level has no texture block at all
        # (s40.pds card 0x20, which is garbage data); callers treat an empty
        # list as "nothing to load", since the model swap is still valid
        # without it.
        "textures": list(data.get("textures", [])),
    }