"""
Disables every vanilla chest that has a known ISO address, by writing a
single zero byte at that address - matching mechanic_ap_key_item_opcode.py's
own convention of direct raw-ISO writes for simple, single-byte/word patches
that don't need any code injection (no cave usage at all).

lost_kingdoms_2_chests is the world's own chest/location table (imported
from Locations.py, a sibling of LK2Client.py - see mechanic_ap_key_item_
opcode.py's own import of STORAGE_ADDRESSES for the same package layout).
Each entry is expected to carry an "isoAddress" key: either "" (no known
ISO address for that chest yet - skipped entirely, matching the source
snippet this was built from) or a hex string (e.g. "0xb1234c8" or
"b1234c8") parsed via int(..., 16).
"""

import logging

from worlds.LostKingdoms2.Locations import lost_kingdoms_2_chests

logger = logging.getLogger()  # root logger, matching ISO_Patcher.py's own convention

ZERO_BYTE = (0).to_bytes(1, byteorder="big")


def apply(patcher):
    patched_count = 0
    skipped_count = 0

    for key, location in lost_kingdoms_2_chests.items():
        iso_address_str = location["isoAddress"]
        if iso_address_str == "":
            skipped_count += 1
            continue

        iso_address = int(iso_address_str, 16)
        patcher.file.seek(iso_address)
        patcher.file.write(ZERO_BYTE)
        patched_count += 1

    logger.info(
        f"[mechanic_disable_vanilla_chests] disabled {patched_count} vanilla chests "
        f"({skipped_count} skipped - no known ISO address)"
    )
