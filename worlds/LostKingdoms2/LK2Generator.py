import json, os
import random
import shutil
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
    def __init__(self, clean_iso_path: str, randomized_output_file_path: str, ap_output_data: bytes, debug_flag=False):
        # Takes note of the provided Randomized Folder path and if files should be exported instead of making an ISO.
        self.debug = debug_flag
        self.clean_iso_path = clean_iso_path
        self.randomized_output_file_path = randomized_output_file_path

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

        self.write_string(iso,0x1E000,0x00000100,0x80003100,0x80003DA0,self.output_data["Name"])

        logger.info("Rom modified")

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
