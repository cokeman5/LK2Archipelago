import logging

NAME_MAX_BYTES = 32

logger = logging.getLogger()  # root logger, matching every other mechanic's own convention

# --- REVISION 2: was previously a fixed, hardcoded NAME_ADDRESS
# (0x80003DA0), which turned out to be a genuine bug - that address
# fell INSIDE the shared cave region (0x800033FC-0x80005330, see
# ISO_Patcher.py's own CAVE_RAM_ADDR/CAVE_SIZE), at offset 0x9A4 into
# it - directly within mechanic_cross_level_monster_loadingscreen.py's
# own cave allocation range. Since that old address was written via a
# direct patch_bytes() call rather than through patcher.alloc_cave(),
# whichever mechanic ran LATER in _apply_mechanics's own sequence
# silently overwrote whatever the other one wrote - almost certainly
# why the name never showed up. NAME_ADDRESS also never appeared
# anywhere in a full decompiled-source search, suggesting it may have
# been stale to begin with (carried over from an older, unrelated
# tool's own different memory layout).
#
# Now claims the cave's own first 32 bytes directly via alloc_cave(),
# instead of a hardcoded address - this mechanic is confirmed to
# always run FIRST in _apply_mechanics, before any other mechanic's
# own alloc_cave() calls, so this call reliably claims
# CAVE_RAM_ADDR itself (the cave's own first byte) every time, and no
# other mechanic can ever allocate over the same space afterward (the
# cave is a simple, sequential bump allocator that never reuses
# already-claimed regions). Since CAVE_RAM_ADDR is itself a fixed
# constant (see ISO_Patcher.py), the resulting address is still
# effectively fixed and predictable in practice, not truly "random" -
# just correctly reserved instead of colliding with something else.


def apply(patcher, output_data):
    name = str(output_data.get("Name", ""))

    # Truncate to fit, encode, then pad with null bytes to a fixed size -
    # standard fixed-size C-string buffer convention. If the game's name
    # display expects different encoding/padding behavior than this, it's
    # the one assumption worth double-checking against the original
    # StringByteFunction.string_to_bytes_with_limit() if names don't show
    # up correctly in-game.
    encoded = name.encode("ascii", errors="replace")[:NAME_MAX_BYTES]
    padded = encoded + b"\x00" * (NAME_MAX_BYTES - len(encoded))

    name_address = patcher.alloc_cave(NAME_MAX_BYTES)
    patcher.patch_bytes(name_address, padded)

    logger.info(f"[mechanic_player_name] Wrote name {name!r} to {hex(name_address)} "
                f"({len(encoded)}/{NAME_MAX_BYTES} bytes used)")