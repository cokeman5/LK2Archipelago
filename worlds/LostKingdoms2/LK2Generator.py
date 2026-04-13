import json, os
import random
import shutil
import struct
from random import Random

import Utils

from worlds.LostKingdoms2 import lost_kingdoms_2_locations, lost_kingdoms_2_chests, lost_kingdoms_2_cards
from worlds.LostKingdoms2.iso_helper.DOL_Updater import update_dol_offsets

from .client.constants import CLIENT_VERSION, AP_WORLD_VERSION_NAME
import logging

logger = logging.getLogger()

RANDOMIZER_NAME = "Lost Kingdoms II"

STARTING_DECK_ADDRESS = 0x16D641


class LK2Randomizer:
    def __init__(self, clean_iso_path: str, randomized_output_file_path: str, ap_output_data: bytes, cardback_gtx: bytes = None, debug_flag=False):
        # Takes note of the provided Randomized Folder path and if files should be exported instead of making an ISO.
        self.debug = debug_flag
        self.clean_iso_path = clean_iso_path
        self.randomized_output_file_path = randomized_output_file_path
        self.cardback_gtx = cardback_gtx
        self.output_data = json.loads(ap_output_data.decode('utf-8'))

        # Set the random's seed for uses in other files.
        self.random = Random()
        local_seed: str = str(self.output_data["Seed"])
        self.random.seed(local_seed)
        new_iso = None

        logger.info(randomized_output_file_path)
        logger.info("Beginning Log Patching Process")
        try:
            new_iso = self.copy_iso(clean_iso_path, randomized_output_file_path, local_seed)
        except IOError:
            logger.error("IO Error")
            raise Exception("'" + randomized_output_file_path + "' is currently in use by another program.")

        # Make sure that the server and client versions match before attempting to patch ISO.
        self._check_server_version(self.output_data)

        # Saves the randomized iso file, with all files updated.
        if new_iso is not None:
            self.write_to_iso(new_iso)

    def copy_iso(self, iso_path, destination, seed):
        # make copy of .iso with filename @newISO
        logger.info("Rom copying to " + destination)
        copy_file(iso_path, destination)
        logger.info("Rom copied to " + destination)
        return destination

    def write_to_iso(self, iso):
        with open(iso, 'r+b') as iso_file:
            for key in lost_kingdoms_2_chests:
                location = lost_kingdoms_2_chests[key]
                if location["isoAddress"] != "":
                    iso_file.seek(int(location["isoAddress"],16))
                    iso_file.write((int("0", 16).to_bytes(1, byteorder='big')))
            self.patch_sp_tex_entry(iso_file)

        self.write_string(iso,0x1E000,0x00000100,0x80003100,0x80003DA0,self.output_data["Name"])

        logger.info("Rom modified")

    import os

    import struct
    import os

    import struct
    import os

    def patch_sp_tex_entry(self, iso_file, entry_index=62):
        # The signature we confirmed at 0x41D04E0
        iso_tex_header_signature = b'\x00\x0c\x2d\xc0\x00\x00\x00\x41\x00\x00\x01\x20\x00\x00\x2a\x80'

        search_start = 0x41D0000
        iso_file.seek(search_start)
        chunk = iso_file.read(4096)
        header_pos = chunk.find(iso_tex_header_signature)

        if header_pos == -1:
            logger.error("Could not find the .TEX container signature.")
            return

        sp_tex_iso_offset = search_start + header_pos

        # 1. Locate Entry 62 in the offset table
        iso_file.seek(sp_tex_iso_offset + 0x08 + (entry_index * 4))
        entry_offset = struct.unpack('>I', iso_file.read(4))[0]
        next_offset = struct.unpack('>I', iso_file.read(4))[0]

        original_total_size = next_offset - entry_offset
        target_address = sp_tex_iso_offset + entry_offset

        # 2. SURGICAL STEP: Read the original entry's header (first 32 bytes)
        # This contains the format, width, height, and mipmap data the game expects.
        iso_file.seek(target_address)
        original_gtx_header = iso_file.read(32)

        # 3. PREPARE PAYLOAD: Use your new pixels but skip its own header
        # We assume your cardback_gtx has its own 32-byte header we want to discard.
        new_pixel_data = self.cardback_gtx[32:]

        # Reconstruct the entry: Original Header + New Pixels
        final_patch = original_gtx_header + new_pixel_data

        # 4. STRICT SIZE ENFORCEMENT
        # We MUST stay within the original byte-count of Entry 62.
        if len(final_patch) > original_total_size:
            logger.warning("Patch too large; truncating to match original entry size.")
            final_patch = final_patch[:original_total_size]
        elif len(final_patch) < original_total_size:
            padding_needed = original_total_size - len(final_patch)
            final_patch += b'\x00' * padding_needed

        # 5. WRITE & VERIFY
        iso_file.seek(target_address)
        iso_file.write(final_patch)
        iso_file.flush()

        iso_file.seek(target_address)
        verification = iso_file.read(4)
        if verification == original_gtx_header[:4]:  # Should still start with 'GTX1'
            logger.info(f"SUCCESS: Surgical patch applied to Entry {entry_index} at {hex(target_address)}")
        else:
            logger.error("FAILURE: Write verification failed.")

    def randomize_starting_deck(self, iso_file):
        cards = list(lost_kingdoms_2_cards.values())
        for x in range(12):
            card = random.choice(cards)
            cards.remove(card)
            iso_file.seek(STARTING_DECK_ADDRESS+x*2)
            iso_file.write(int(card["hexCode"], 16).to_bytes(1, byteorder='big'))

    def write_string(self, iso_path: str,main_dol_iso_offset: int,section_file_offset: int,section_ram: int,target_ram: int,text: str,max_len: int = 64):

        delta = target_ram - section_ram
        dol_offset2 = section_file_offset + delta
        iso_offset = main_dol_iso_offset + dol_offset2

        data = text.encode("ascii")[:max_len]
        data += b"\x00" * (max_len - len(data))

        with open(iso_path, "r+b") as f:
            f.seek(iso_offset)
            f.write(data)

    def write_string_fixed(iso_file, offset: int, text: str, max_len: int = 64):
        # Encode to bytes (ASCII is usually correct for player names)
        raw = text.encode("ascii", errors="ignore")

        # Truncate if too long
        raw = raw[:max_len]

        # Pad with null bytes
        raw = raw.ljust(max_len, b"\x00")

        iso_file.seek(offset)
        iso_file.write(raw)

    def _check_server_version(self, output_data):
        """
        Compares the version provided in the patch manifest against the client's version.

        :param output_data: The manifest's output data which we attempt to acquire the generated version.
        """
        ap_world_version = "<0.5.6"

        if AP_WORLD_VERSION_NAME in output_data:
            ap_world_version = output_data[AP_WORLD_VERSION_NAME]
        if ap_world_version != CLIENT_VERSION:
            raise Utils.VersionException("Error! Server was generated with a different Lost Kingdoms 2 " +
                                         f"APWorld version.\nThe client version is {CLIENT_VERSION}!\nPlease verify you are using the " +
                                         f"same APWorld as the generator, which is '{ap_world_version}'")

    def save_randomized_iso(self):
        update_dol_offsets(self)

def copy_file(source_path, destination_path):
    try:
        # Open source file in read-binary mode
        with open(source_path, 'rb') as src_file:
            # Open destination file in write-binary mode ('wb')
            # 'wb' creates the file if it doesn't exist, and overwrites if it does
            with open(destination_path, 'wb') as dst_file:
                # Read from source and write to destination in chunks (e.g., 4KB buffer)
                while True:
                    chunk = src_file.read(4096)  # Read 4096 bytes
                    if not chunk:
                        break  # End of file
                    dst_file.write(chunk)
        print(f"File copied from '{source_path}' to '{destination_path}' successfully.")
    except FileNotFoundError:
        print(f"Error: Source file '{source_path}' not found.")
    except PermissionError:
        print(f"Error: Permission denied when accessing files.")
    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == '__main__':
    print("Run this from Launcher.py instead.")
