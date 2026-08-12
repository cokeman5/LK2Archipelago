"""
Patches every level exit's own "which level unlocks next" value into
the ISO directly, replacing the runtime write_memory() approach - see
project history: a runtime write only affects the currently-loaded,
in-memory copy of a level's own data blob, which gets silently
re-populated from the ORIGINAL, unmodified level file every time that
level reloads. The value needs to live in the level file itself on
disc to actually stick.

Reads directly from lost_kingdoms_2_region_exits (exit -> {level,
address}) - the vanilla level ID used for the pre-write safety check
(matching mechanic_code_modifications.py's own TEXT_PATCHES
convention) is derived from lost_kingdoms_2_regions[level]["levelID"]
rather than duplicated separately.

MIRROR_ADDRESSES: three ISO addresses hold separate "level ID to
load" (or, for Gromtull Desert, an alternate "road to Jarvi's House"
entrance) fields that mirror a primary exit's own value but aren't
represented in lost_kingdoms_2_region_exits at all - confirmed
directly against the source CSV that each one's own vanilla value
already matches its primary exit's vanilla value exactly. Each gets
the SAME new value written right after its own primary exit, with its
own independent safety check.
"""

from ..Locations import lost_kingdoms_2_regions, lost_kingdoms_2_region_exits
from .. import randomize_exits
import random

# NOPs whatever conditional normally hides the world map's own
# region-connection arrows - with level connections randomized, the
# vanilla logic for when an arrow should be visible presumably no
# longer lines up with the actual, randomized connections, so this
# makes every arrow always visible instead.
ALWAYS_SHOW_ARROWS_ADDR = 0x800a69a8

MIRROR_ADDRESSES = {
    "Kadishu Exit 1": (0x07792200, 41),
    "Grenfoel Cathedral Exit 2": (0x0A730ED8, 42),
    "Gromtull Desert Exit 1": (0x07792188, 40),
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
    random.seed(output_data.get("Seed", -1) + 4)

    patcher.patch_word(ALWAYS_SHOW_ARROWS_ADDR, 0x60000000)

    level_ordering = randomize_exits()

    for exit_name, exit_info in lost_kingdoms_2_region_exits.items():
        iso_addr = int(exit_info["address"], 16)
        vanilla_level_id = lost_kingdoms_2_regions[exit_info["level"]]["levelID"]
        new_level_id = lost_kingdoms_2_regions[level_ordering[exit_name]]["levelID"]

        _write_checked(patcher, iso_addr, vanilla_level_id, new_level_id, exit_name)

        if exit_name in MIRROR_ADDRESSES:
            mirror_addr, mirror_vanilla_id = MIRROR_ADDRESSES[exit_name]
            _write_checked(patcher, mirror_addr, mirror_vanilla_id, new_level_id, f"{exit_name} (mirror)")