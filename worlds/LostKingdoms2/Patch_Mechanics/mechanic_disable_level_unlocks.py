"""
Patches every level exit's own "which level unlocks next" value into
the ISO directly, setting all of them to 0 rather than randomizing
them - so no level ever unlocks upon completion. Same direct-to-ISO
approach as mechanic_randomize_level_unlocks.py (see that file's own
docstring for why a runtime write_memory() isn't enough: it only
affects the currently-loaded, in-memory copy of a level's own data
blob, which gets silently re-populated from the ORIGINAL, unmodified
level file every time that level reloads - the value needs to live in
the level file itself on disc to actually stick).

Reads directly from lost_kingdoms_2_region_exits (exit -> {level,
address}) - the vanilla level ID used for the pre-write safety check
is derived from lost_kingdoms_2_regions[level]["levelID"], same as
mechanic_randomize_level_unlocks.py.

MIRROR_ADDRESSES: three ISO addresses hold separate "level ID to
load" (or, for Gromtull Desert, an alternate "road to Jarvi's House"
entrance) fields that mirror a primary exit's own value but aren't
represented in lost_kingdoms_2_region_exits at all - same three
addresses as mechanic_randomize_level_unlocks.py, each getting the
same new value (0) written right after its own primary exit, with its
own independent safety check.
"""

from ..Locations import lost_kingdoms_2_regions, lost_kingdoms_2_region_exits

# NOPs whatever conditional normally hides the world map's own
# region-connection arrows - with every exit's own unlock value set to
# 0, the vanilla logic for when an arrow should be visible no longer
# lines up with the actual (lack of) connections, so this makes every
# arrow always visible instead. Same patch, same address, as
# mechanic_randomize_level_unlocks.py.
ALWAYS_SHOW_ARROWS_ADDR = 0x800a69a8

MIRROR_ADDRESSES = {
    "Kadishu Exit 1": (0x07792200, 41),
    "Grenfoel Cathedral Exit 2": (0x0A730ED8, 42),
    "Gromtull Desert Exit 1": (0x07792188, 40),
}

# --- Royal Tower, Lower's own unlock (levelID 12, later reloading as
# levelID 18 partway through - see this mechanic's own investigation
# history for the full trace) is NOT represented anywhere in
# lost_kingdoms_2_region_exits at all, since Alanjeh Castle connects
# to it via a fixed, hardcoded source in __init__.py's own
# create_regions(), not through the normal, randomizable exit system.
# Unlike every other exit, there is no separate DATA byte anywhere
# that determines this target - the offset itself (770 = 0x302,
# i.e. base 0x8025dbcc + levelID 12 * 0x40 + 2) is a hardcoded,
# literal immediate baked directly into these two `stb` instructions
# in main.dol's own compiled code, confirmed via a live write-
# breakpoint on 0x8025dece while beating Alanjeh Castle (levelID 11)
# in-game. NOPing them prevents Royal Tower, Lower from ever getting
# unlocked as a side effect of completing Alanjeh Castle, consistent
# with every other exit in this file being disabled the same way.
ALANJEH_CASTLE_UNLOCK_ROYAL_TOWER_ADDRS = [0x8007a3b4, 0x8007a3bc]

# --- Completing Alanjeh Castle (levelID 11) also runs a loop, within
# this same function, over every levelID from some start up to 90,
# EXCLUDING 12 and 18 specifically (see cmpwi checks at 0x8007a3c4/
# 0x8007a3cc, right before this loop's own body) - for every level it
# doesn't skip, it reads that level's own unlock byte (same table,
# same "+2" offset as everything else in this file), sets bit 6
# (value 0x40) in it, and writes it back. Confirmed via main.dol that
# bit 6 is checked elsewhere (e.g. 0x800a62a8's own surrounding code)
# with an immediate `bclr` (conditional early-return) right after the
# test - i.e. bit 6 means "this level is blocked," distinct from bit
# 7 (0x80, "unlocked," the one ALWAYS_SHOW_ARROWS_ADDR's own code
# checks) and bit 5 (0x20, the second bit set alongside 0x80 for
# levelID 12/18 specifically, at ALANJEH_CASTLE_UNLOCK_ROYAL_TOWER_
# ADDRS above). This is confirmed to be the actual mechanism behind
# every other, previously-unlocked level becoming unselectable right
# after beating Alanjeh Castle. NOPing the one `stb` that persists
# this bit (rather than the whole loop) is the minimal change: the
# loop's own bounds-check/increment logic is left completely intact,
# it just no longer writes anything back for each level it visits.
ALANJEH_CASTLE_BLOCK_OTHER_LEVELS_ADDR = 0x8007a3f0

# --- Royal Tower, Middle -> Royal Tower, Upper (levelID 15 -> 16) is
# an ordinary, data-driven script instruction (opcode 406/"0196"),
# same as every other, normal exit in lost_kingdoms_2_region_exits,
# just not represented there since Royal Tower's own progression
# connects via fixed, hardcoded sources in __init__.py's own
# create_regions(), not the randomizable exit system.
#
# Royal Tower, Lower/12 -> Royal Tower, Middle (levelID 12 -> 15) is
# ALSO ordinary and data-driven, but via a DIFFERENT opcode (134/
# "0086", argcount 1, template "86 00 01 00 04 00 00" then the 4-byte
# target levelID) - confirmed via a live breakpoint on the actual
# "populate a new script thread" function (0x8008a7e0), since this
# opcode's own runtime argument pointer lives in a reused, constantly-
# changing scratch buffer (DAT_8025f740-based), not a stable address a
# breakpoint could sit on directly. Lives in s12.pds (levelID 12, the
# FIRST half of Royal Tower, Lower - see this mechanic's own docstring
# above on why level 12 reloads as level 18 partway through), not
# s18.pds. Confirmed via live testing to exist TWICE, at two separate
# offsets, each the start of its own, separate script sequence that
# otherwise diverges afterward (one continues into an opcode 406 call,
# the other into an opcode 160 call) - both begin with the identical
# "opcode 134 -> unlock 15, opcode 132 -> (unrelated, targets 18)"
# instruction pair, so either one alone could fire the unlock; both
# must be zeroed to fully disable it.
#
# STANDARD_UNLOCK_ADDRESSES's own vanilla ID is the CURRENT level's
# own target (matching _write_checked()'s own pre-write safety
# check), keyed by a short label for logging.
STANDARD_UNLOCK_ADDRESSES = {
    "Royal Tower, Middle -> Royal Tower, Upper": (0x0ABDD560, 16),
    "Royal Tower, Lower/12 -> Royal Tower, Middle (instance 1)": (0x0B94E200 , 15),
    "Royal Tower, Lower/12 -> Royal Tower, Middle (instance 2)": (0x0B94E3B4 , 15),
}


def _write_checked(patcher, iso_addr, vanilla_level_id, new_level_id, label):
    expected_bytes = vanilla_level_id.to_bytes(4, byteorder="big")
    patcher.file.seek(iso_addr)
    original = patcher.file.read(4)
    if original != expected_bytes:
        raise ValueError(
            f"Expected level ID {vanilla_level_id} for {label!r} at ISO offset {hex(iso_addr)}, "
            f"found {original!r} instead. Aborting rather than overwrite something unexpected."
        )
    patcher.file.seek(iso_addr)
    patcher.file.write(new_level_id.to_bytes(4, byteorder="big"))


def apply(patcher, output_data):
    patcher.patch_word(ALWAYS_SHOW_ARROWS_ADDR, 0x60000000)

    for addr in ALANJEH_CASTLE_UNLOCK_ROYAL_TOWER_ADDRS:
        patcher.patch_word(addr, 0x60000000)

    patcher.patch_word(ALANJEH_CASTLE_BLOCK_OTHER_LEVELS_ADDR, 0x60000000)

    for label, (iso_addr, vanilla_level_id) in STANDARD_UNLOCK_ADDRESSES.items():
        _write_checked(patcher, iso_addr, vanilla_level_id, 0, label)

    for exit_name, exit_info in lost_kingdoms_2_region_exits.items():
        iso_addr = int(exit_info["address"], 16)
        vanilla_level_id = lost_kingdoms_2_regions[exit_info["level"]]["levelID"]

        _write_checked(patcher, iso_addr, vanilla_level_id, 0, exit_name)

        if exit_name in MIRROR_ADDRESSES:
            mirror_addr, mirror_vanilla_id = MIRROR_ADDRESSES[exit_name]
            _write_checked(patcher, mirror_addr, mirror_vanilla_id, 0, f"{exit_name} (mirror)")