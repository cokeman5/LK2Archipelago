import struct
from pkgutil import get_data
from typing import TYPE_CHECKING

from ..Helper_Functions import StringByteFunction as sbf

if TYPE_CHECKING:
    from ..LK2Generator import LostKingdoms2Randomizer

CUSTOM_CODE_OFFSET_START = 0x39FA20
LM_PLAYER_NAME_BYTE_LENGTH = 64

# Updates the main DOL file, which is the main file used for GC and Wii games. This section includes some custom code
# inside the DOL file itself.
def update_dol_offsets(lm_gen: "LostKingdoms2Randomizer"):
    # Define all variables from the output data
    slot_name: str = str(lm_gen.output_data["Name"])

    # Find the main DOL file and read it.
    import gclib.dol
    from gclib.dol import DOL
    lm_dol = DOL()
    dol_data = lm_gen.gcm.read_file_data("sys/main.dol")
    lm_dol.read(dol_data)

    # Store Player name
    lm_player_name = str(slot_name).strip()
    lm_dol.data.seek(0x324740)
    lm_dol.data.write(sbf.string_to_bytes_with_limit(lm_player_name, LM_PLAYER_NAME_BYTE_LENGTH))


    # Save all changes to the DOL itself.
    lm_dol.save_changes()
    lm_gen.gcm.changed_files["sys/main.dol"] = lm_dol.data