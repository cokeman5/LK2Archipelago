import os
import threading
import typing
from dataclasses import fields
from typing import Optional

from BaseClasses import MultiWorld
from worlds.AutoWorld import WebWorld, World
from .client.constants import AP_WORLD_VERSION_NAME, CLIENT_VERSION
from .client.lostkingdoms2_settings import LostKingdoms2Settings
from ..LauncherComponents import launch_subprocess, components, Component, SuffixIdentifier, icon_paths, Type

from .Items import *
from .Locations import *
from .LK2Options import *
from .iso_helper.lk2_rom import LK2PlayerContainer


def run_client(*args):
    from .LK2Client import main  # lazy import
    launch_subprocess(main, name="LK2Client", args=args)

# Adds the launcher for our component and our client logo.
components.append(
    Component("Lost Kingdoms II Client", func=run_client, component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".aplm"), icon="Archipelago_Icon"))
icon_paths["Archipelago_Icon"] = f"ap:{__name__}/data/Archipelago_Icon.png"

class LostKingdoms2Web(WebWorld):
    theme = "jungle"


class LostKingdoms2World(World):
    """
    Lost Kingdoms II, known as 'Rune II: Koruten no Kagi no Himitsu' in Japan, is a 2003 action role-playing game developed by FromSoftware and published by Activision. It is the sequel to Lost Kingdoms. Lost Kingdoms II is a card-based action role-playing game where battles are fought in real-time.
    """

    game = "Lost Kingdoms II"

    options_dataclass = LK2Options.LostKingdoms2Options  # options the player can set
    options: LostKingdoms2Options  # typing hints for option results
    settings: typing.ClassVar[LostKingdoms2Settings]  # will be automatically assigned from type hint
    topology_present = True  # show path to required location checks in spoiler

    # The following two dicts are required for the generation to know which
    # items exist. They could be generated from json or something else. They can
    # include events, but don't have to since events will be placed manually.

    item_name_to_id = {}
    for key in lost_kingdoms_2_items:
        item_name_to_id[key] = lost_kingdoms_2_items[key]["number"]

    #id_to_item_name = {}
    #for item_id_index in range(len(lost_kingdoms_2_items)):
    #    item_name_to_id[base_id + item_id_index] = lost_kingdoms_2_items[item_id_index]

    location_name_to_id = {}
    for key in lost_kingdoms_2_locations:
        location_name_to_id[key] = lost_kingdoms_2_locations[key]["id"]

    # Items can be grouped using their names to allow easy checking if any item
    # from that group has been collected. Group names can also be used for !hint
    item_name_groups = {
        "weapons": {"red_fairy", "world", "shop", "key_item"},
    }

    def __init__(self, multiworld: MultiWorld, player: int):
        super(LostKingdoms2World, self).__init__(multiworld, player)
        self.win_condition : Optional[int] = 0

    def create_item(self, item: str) -> LK2Item:

        classification = ItemClassification.filler
        item_data = lost_kingdoms_2_items[item]
        return LK2Item(item, classification, item_data, self.player)

    def create_items(self) -> None:
        # Add items to the Multiworld.
        # If there are two of the same item, the item has to be twice in the pool.
        # Which items are added to the pool may depend on player options, e.g. custom win condition like triforce hunt.
        # Having an item in the start inventory won't remove it from the pool.
        # If you want to do that, use start_inventory_from_pool

        for item in map(self.create_item, lost_kingdoms_2_items):
            self.multiworld.itempool.append(item)

        # itempool and number of locations should match up.
        # If this is not the case we want to fill the itempool with junk.
        junk = 0  # calculate this based on player options
        self.multiworld.itempool += [self.create_item("nothing") for _ in range(junk)]

    def generate_early(self) -> None:

        self.win_condition = self.options.win_condition

        starting_inventory = {"Hobgoblin", "Hobgoblin", "Hobgoblin", "Lizardman", "Lizardman", "Lizardman",
                              "Mandragora", "Mandragora", "Mandragora", "Fairy", "Dragon Knight"}
        for item in starting_inventory:
            self.multiworld.push_precollected(self.create_item(item))

    def create_regions(self):
        menu_region = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu_region)

        for region in lost_kingdoms_2_regions:
            new_region = Region(region, self.player, self.multiworld)
            self.multiworld.regions.append(new_region)
            menu_region.connect(new_region)

        for key in lost_kingdoms_2_locations:
            region = self.multiworld.get_region(lost_kingdoms_2_locations[key]["level"], self.player)
            location = lost_kingdoms_2_locations[key]
            location_data = LK2LocationData(location["isoAddress"],location["missable"],
                                            location["RAMAddress"],location["bitOffset"],
                                            location["id"])
            region.locations.append(LK2Location(self.player,key, region, location_data))

    def set_rules(self) -> None:
        pass

    def generate_output(self, output_directory: str):
        # Output seed name and slot number to seed RNG in randomizer client
        # noinspection PyDictCreation
        output_data = {
            "Seed": self.multiworld.seed,
            "Slot": self.player,
            "Name": self.player_name,
            #"Locations":{},
            AP_WORLD_VERSION_NAME: CLIENT_VERSION
        }

        #for key in lost_kingdoms_2_locations:
        #    item_info = {
        #                    "player": self.player,
        #                    "name": lost_kingdoms_2_locations[key]["cardName"],
        #                    "game": self.game,
        #                    "type": "card"
        #                }
        #    output_data["Locations"][key] = item_info

        # Outputs the plando details to our expected output file
        # Create the output path based on the current player + expected patch file ending.
        patch_path = os.path.join(output_directory, f"{self.multiworld.get_out_file_name_base(self.player)}"
                                                    f"{LK2PlayerContainer.patch_file_ending}")
        # Create a zip (container) that will contain all the necessary output files for us to use during patching.
        lm_container = LK2PlayerContainer(output_data, patch_path, self.multiworld.player_name[self.player], self.player)
        # Write the expected output zip container to the Generated Seed folder.
        lm_container.write()


