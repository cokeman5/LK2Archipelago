import asyncio
import sys
import time
import traceback
from typing import TYPE_CHECKING, Any, Optional

import dolphin_memory_engine
from .client.constants import *

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop
from .iso_helper.lk2_rom import LK2USAAPPatch

from .Locations import lost_kingdoms_2_locations, lost_kingdoms_2_regions, lost_kingdoms_2_combos
from worlds.LostKingdoms2 import lost_kingdoms_2_cards, lost_kingdoms_2_key_items, lost_kingdoms_2_items, \
    location_name_to_id

if TYPE_CHECKING:
    import kvui

CONNECTION_REFUSED_GAME_STATUS = (
    "Dolphin failed to connect. Please load a randomized ROM for Lost Kingdoms 2. Trying again in 5 seconds..."
)
CONNECTION_REFUSED_SAVE_STATUS = (
    "Dolphin failed to connect. Please load into the save file. Trying again in 5 seconds..."
)
CONNECTION_LOST_STATUS = (
    "Dolphin connection was lost. Please restart your emulator and make sure Lost Kingdoms 2 is running."
)
CONNECTION_CONNECTED_STATUS = "Dolphin connected successfully."
CONNECTION_INITIAL_STATUS = "Dolphin connection has not been initiated."

SLOT_NAME_ADDR = 0x80003DA0
IS_IN_GAME_ADDR = 0x80223c88

RED_FAIRY_COUNT_ADDRESS = 0x8025d032
KEY_ITEM_ITEM_ADDRESS = 0x8025d068
KEY_ITEM_LOCATION_ADDRESS = 0x80003edc
MAGIC_BOOSTER_ADDRESS = 0x8025dd90
Valkyrie_Ashura_ADDRESS = 0x8025e28c
God_of_Harmony_Health_ADDRESS = 0x80223eb8
God_of_Harmony_ID_ADDRESS = 0x80223e5c # = 8103a040
Emporer_Health_ADDRESS = 0x80223fb8
Emperor_ID_ADDRESS = 0x80223f6c # = 8153e580


NUM_ITEMS_RECEIVED = 0

ONE_TIME_MODIFIERS = False


# This address is used to check/set the player's health for DeathLink.
CURR_HEALTH_ADDR = 0x80223c98


class LK2CommandProcessor(ClientCommandProcessor):
    """
    Command Processor for Lost Kingdoms 2 client commands.

    This class handles commands specific to Lost Kingdoms 2.
    """

    def __init__(self, ctx: CommonContext):
        """
        Initialize the command processor with the provided context.

        :param ctx: Context for the client.
        """
        super().__init__(ctx)

    def _cmd_dolphin(self) -> None:
        """
        Display the current Dolphin emulator connection status.
        """
        if isinstance(self.ctx, LK2Context):
            logger.info(f"Dolphin Status: {self.ctx.dolphin_status}")


class LK2Context(CommonContext):
    """
    The context for Lost Kingdoms 2 client.

    This class manages all interactions with the Dolphin emulator and the Archipelago server for Lost Kingdoms 2.
    """

    command_processor = LK2CommandProcessor
    game: str = "Lost Kingdoms II"
    items_handling: int = 0b111  # full remote
    slot: str

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        """
        :param server_address: Address of the Archipelago server.
        :param password: Password for server authentication.
        """

        super().__init__(server_address, password)
        self.dolphin_sync_task: Optional[asyncio.Task[None]] = None
        self.dolphin_status: str = CONNECTION_INITIAL_STATUS
        self.awaiting_rom: bool = False
        self.has_send_death: bool = False
        self.send_hints: int = 0
        self.hints = {}
        self.slot_data = {}

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        """
        Disconnect the client from the server and reset game state variables.

        :param allow_autoreconnect: Allow the client to auto-reconnect to the server. Defaults to `False`.

        """
        await super().disconnect(allow_autoreconnect)

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        """
        Handle incoming packages from the server.

        :param cmd: The command received from the server.
        :param args: The command arguments.
        """
        if cmd == "Connected":
            self.slot_data = args["slot_data"]
            if "death_link" in args["slot_data"]:
                Utils.async_start(self.update_death_link(bool(args["slot_data"]["death_link"])))

    def on_deathlink(self, data: dict[str, Any]) -> None:
        """
        Handle a DeathLink event.

        :param data: The data associated with the DeathLink event.
        """
        super().on_deathlink(data)
        _give_death(self)

    def make_gui(self) -> type["kvui.GameManager"]:
        """
        Initialize the GUI for Lost Kingdoms 2  client.

        :return: The client's GUI.
        """
        ui = super().make_gui()
        ui.base_title = "Archipelago Lost Kingdoms 2 Client"
        return ui

    async def wait_for_next_loop(self, time_to_wait: float):
        await asyncio.sleep(time_to_wait)

    async def server_auth(self, password_requested: bool = False) -> None:
        """
        Authenticate with the Archipelago server.

        :param password_requested: Whether the server requires a password. Defaults to `False`.
        """
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            if self.awaiting_rom:
                return
            self.awaiting_rom = True
            logger.info("Awaiting connection to Dolphin to get player information.")
            return
        await self.send_connect()


def read_memory(console_address: int, byte_size: int = 2) -> int:
    """
    Read a 2-byte short from Dolphin memory.

    :param byte_size: The size of the data to read in bytes.
    :param console_address: Address to read from.
    :return: The value read from memory.
    """
    return int.from_bytes(dolphin_memory_engine.read_bytes(console_address, byte_size), byteorder="big")


def write_memory(console_address: int, value: int, byte_size: int = 2) -> None:
    """
    Write a 2-byte short to Dolphin memory.

    :param byte_size: The size of the memory to write in bytes
    :param console_address: Address to write to.
    :param value: Value to write.
    """
    dolphin_memory_engine.write_bytes(console_address, value.to_bytes(byte_size, byteorder="big"))


def read_string(console_address: int, strlen: int) -> str:
    """
    Read a string from Dolphin memory.

    :param console_address: Address to start reading from.
    :param strlen: Length of the string to read.
    :return: The string.
    """
    string = dolphin_memory_engine.read_bytes(console_address, strlen).split(b"\0", 1)[0].decode()
    logger.info("string read: " + str(string))
    return string


def _give_death(ctx: LK2Context) -> None:
    """
    Trigger the player's death in-game by setting their current health to zero.

    :param ctx: The Lost Kingdoms 2 client context.
    """
    if (
        ctx.slot is not None
        and dolphin_memory_engine.is_hooked()
        and ctx.dolphin_status == CONNECTION_CONNECTED_STATUS
        and check_ingame()
    ):
        ctx.has_send_death = True
        write_memory(CURR_HEALTH_ADDR, 0)


def _give_item(ctx: LK2Context, item_name: str) -> bool:
    """
    Give an item to the player in-game.

    :param ctx: Lost Kingdoms 2 client context.
    :param item_name: Name of the item to give.
    :return: Whether the item was successfully given.
    """
    item = lost_kingdoms_2_items.get(item_name, None)
    if item is None:
        return False
    elif item["Type"] == "Card":
        return give_card(item_name)
    elif item["Type"] == "Red Fairy":
        return give_red_fairy()
    elif item["Type"] == "Key Item":
        return give_key_item(item_name)
    elif item["Type"] == "Magic Boosters":
        return activate_magic_boosters()
    else:
        logger.error("Received Invalid Item:" + item_name + " " + str(item_name))
        return False

def give_red_fairy() -> bool:
    logger.info("Giving fairy")
    try:
        memory_address = RED_FAIRY_COUNT_ADDRESS
        current_amount_of_item = read_memory(memory_address, 1)
        write_memory(memory_address, current_amount_of_item + 1,1)
        global NUM_ITEMS_RECEIVED
        NUM_ITEMS_RECEIVED+=1
        return True
    except Exception as e:
        logger.error(e)
        return False

def give_card(card_name: str) -> bool:
    logger.info("Giving card" + card_name)
    try:
        memory_address = int(lost_kingdoms_2_cards[card_name]["DolphinAddress"], 16)
        current_amount_of_item = read_memory(memory_address)
        write_memory(memory_address, current_amount_of_item + 1)
        global NUM_ITEMS_RECEIVED
        NUM_ITEMS_RECEIVED += 1
        return True
    except Exception as e:
        logger.error(e)
        return False

def give_key_item(item_name: str) -> bool:
    logger.info("Giving key item" + item_name)
    try:
        offset = 0
        for key_item in lost_kingdoms_2_key_items:
            offset += 1
            if key_item == item_name:
                break
        value = read_memory(KEY_ITEM_ITEM_ADDRESS,4)
        write_memory(KEY_ITEM_ITEM_ADDRESS, value | (1 << offset), 4)

        match item_name:
            case "Blue Key":
                write_memory(0x8025d897, 0)
                write_memory(0x8025d8a7, 0)
                write_memory(0x8025d8b7, 0)
                value = read_memory(0x8025dcd1, 1)
                write_memory(0x8025dcd0, value | (1 << 0))
            case "Red Key":
                write_memory(0x8025d867, 0)
                write_memory(0x8025d877, 0)
                write_memory(0x8025d887, 0)
                value = read_memory(0x8025dcd1, 1)
                write_memory(0x8025dcd0, value | (1 << 1))
            case "Green Key":
                write_memory(0x8025d8c7, 0)
                write_memory(0x8025d8d7, 0)
                value = read_memory(0x8025dcd1, 1)
                write_memory(0x8025dcd0, value | (1 << 2))

        global NUM_ITEMS_RECEIVED
        NUM_ITEMS_RECEIVED += 1
        return True
    except Exception as e:
        logger.error(e)
        return False

def activate_magic_boosters() -> bool:
    value = read_memory(MAGIC_BOOSTER_ADDRESS)
    write_memory(0x8025dd90,value | 1 << 3)
    return True

def modify_code():
    # Change the key item location addresses so the locations can be checked
    # even after receiving the key items.

    #Key locations
    write_memory(0x8006e77c, 0x3CA08000, 4)
    write_memory(0x8006e780, 0x38A53E80, 4)
    #Fossil locations
    write_memory(0x8006e7b8, 0x3C608000, 4)
    write_memory(0x8006e7bc, 0x38633E24, 4)
    #Magic Boosters
    write_memory(0x8008816c, 0x3CC08000, 4)
    write_memory(0x80088174, 0x60C63EE8, 4)
    #Remove the branch preventing duplicates in shops
    write_memory(0x800dc438, 0x60000000, 4)

    logger.info("Modified code")

def set_shop_contents_to_AP():
    for x in range(40):
        write_memory(0x80168700+(x*0x2), 0x00000000)

def open_world():
        for region in lost_kingdoms_2_regions:
            write_memory(lost_kingdoms_2_regions[region]["RAMAddress"], -128, 1)

async def check_victory_conditions(ctx: LK2Context):
    match ctx.slot_data.get("open_world", -1):
        case 0:
            if read_memory(God_of_Harmony_Health_ADDRESS) == 0 and read_memory(God_of_Harmony_ID_ADDRESS,4) == 0x8103a040:
                _give_item(ctx,"Victory")
        case 1:
            if read_memory(Emporer_Health_ADDRESS) == 0 and read_memory(Emperor_ID_ADDRESS,4) == 0x8153e580:
                _give_item(ctx, "Victory")
        case 2:
            for key in lost_kingdoms_2_cards:
                if read_memory(lost_kingdoms_2_cards[key]) <= 0:
                    return
            _give_item(ctx, "Victory")

async def give_items(ctx: LK2Context) -> None:
    """
    Give the player all outstanding items they have yet to receive.

    :param ctx: Lost Kingdoms 2 client context.
    """
    received_items = ctx.items_received
    global NUM_ITEMS_RECEIVED
    if len(received_items) <= NUM_ITEMS_RECEIVED:
        return
    pass

    for x, item in enumerate(received_items[NUM_ITEMS_RECEIVED:], start=NUM_ITEMS_RECEIVED):
        item_name = None
        for lk2_item in lost_kingdoms_2_items:
            if lost_kingdoms_2_items[lk2_item]["id"] == item.item:
                item_name = lk2_item
                break
        logger.info(item.item)
        logger.info(item_name)
        if item_name is not None:
            while not _give_item(ctx, item_name):
                await asyncio.sleep(0.01)
        else:
            logger.error("Invalid item id" + str(item.item))

def check_regular_location(ctx: LK2Context, location: str) -> bool:
    """
    Check that the player has checked a given location.
    This function handles locations that only require checking that a particular bit is set.

    The check looks at the saved data for the stage at which the location is located and the data for the current stage.
    In the latter case, this data includes data that has not yet been written to the saved data.

    :param location: The location.
    :param ctx: Lost Kingdoms 2 client context.
    :raises NotImplementedError: If a location with an unknown type is provided.
    """
    match lost_kingdoms_2_locations[location]["type"]:
        case "Chest" | "Red Fairy" | "Magic Boosters":
            if lost_kingdoms_2_locations[location]["RAMAddress"]!="":
                if (location == "help valkyrie") | (location == "help ashura"):
                    if read_memory(Valkyrie_Ashura_ADDRESS) != 256:
                        return False
                elif "FH - collect" in location:
                    memory_value = read_memory(int(lost_kingdoms_2_locations[location]["RAMAddress"], 16),1)
                    return memory_value >= lost_kingdoms_2_locations[location]["bitOffset"]
                memory_value = read_memory(int(lost_kingdoms_2_locations[location]["RAMAddress"], 16))
                if lost_kingdoms_2_locations[location]["bitOffset"] >= 1:
                    bit_value = (memory_value & (1 << lost_kingdoms_2_locations[location]["bitOffset"]))
                    return bit_value != 0
                else:
                    return False
            else:
                return False
        case "Key Item":
            memory_value = read_memory(KEY_ITEM_LOCATION_ADDRESS)
            bit_value = (memory_value & (1 << lost_kingdoms_2_locations[location]["bitOffset"]))
            return bit_value != 0
        case "Combo":
            memory_value = read_memory(0x8025d070, 8)
            bit_value = (memory_value & (1 << lost_kingdoms_2_combos[location]["bitOffset"]))
            return bit_value != 0

    return False

async def check_locations(ctx: LK2Context) -> set[int]:
    """
    Iterate through all locations and check whether the player has checked each location.

    Update the server with all newly checked locations since the last update. If the player has completed the goal,
    notify the server.

    :param ctx: The Lost Kingdoms 2 client context.
    """

    # Loop through all locations to see if each has been checked.
    for key in lost_kingdoms_2_locations:
        if check_regular_location(ctx, key):
            ctx.locations_checked.add(location_name_to_id[key])
            if lost_kingdoms_2_locations[key]["type"] == "Red Fairy":
                write_memory(int("8025d032",16), read_memory(int("8025d032",16)-1))

    # Send the list of newly-checked locations to the server.
    locations_checked = ctx.locations_checked.difference(ctx.checked_locations)
    if locations_checked:
        logger.info("sending newly checked locations: " + str(locations_checked))
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": list(locations_checked)}])
        ctx.checked_locations.update(locations_checked)
    return locations_checked

async def check_alive() -> bool:
    """
    Check if the player is currently alive in-game.

    :return: `True` if the player is alive, otherwise `False`.
    """
    cur_health = read_memory(CURR_HEALTH_ADDR)
    return cur_health > 0


async def check_death(ctx: LK2Context) -> None:
    """
    Check if the player is currently dead in-game.
    If DeathLink is on, notify the server of the player's death.

    :return: `True` if the player is dead, otherwise `False`.
    """
    if ctx.slot is not None and check_ingame():
        cur_health = read_memory(CURR_HEALTH_ADDR)
        if cur_health <= 0:
            if not ctx.has_send_death and time.time() >= ctx.last_death_link + 3:
                ctx.has_send_death = True
                await ctx.send_death(ctx.player_names[1] + " ran out of hearts.")
        else:
            ctx.has_send_death = False


def check_ingame() -> bool:
    """
    Check if the player is currently in-game.

    :return: `True` if the player is in-game, otherwise `False`.
    """
    return read_memory(IS_IN_GAME_ADDR, 2) != 0


async def dolphin_sync_task_main_task(ctx: LK2Context):
    """
    The task loop for managing the connection to Dolphin.

    While connected, read the emulator's memory to look for any relevant changes made by the player in the game.

    :param ctx: Lost Kingdoms 2 client context.
    """
    global ONE_TIME_MODIFIERS
    logger.info("Starting Dolphin connector. Use /dolphin for status information." + str(ctx.auth))
    logger.info("auth is:" + str(ctx.auth))
    sleep_time = 0.0
    while not ctx.exit_event.is_set():
        if sleep_time > 0.0:
            try:
                # ctx.watcher_event gets set when receiving ReceivedItems or LocationInfo, or when shutting down.
                await asyncio.wait_for(ctx.watcher_event.wait(), sleep_time)
            except asyncio.TimeoutError:
                pass
            sleep_time = 0.0
        ctx.watcher_event.clear()

        try:
            if dolphin_memory_engine.is_hooked() and ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                if ctx.slot is not None:
                    if not ONE_TIME_MODIFIERS:
                        modify_code()
                        if ctx.slot_data.get("open_world", 0):
                            open_world()
                        if ctx.slot_data.get("shopsanity", 0):
                            set_shop_contents_to_AP()
                        ONE_TIME_MODIFIERS = True
                    if "DeathLink" in ctx.tags:
                        await check_death(ctx)
                    await check_victory_conditions(ctx)
                    await give_items(ctx)
                    await check_locations(ctx)
                else:
                    if not ctx.auth:
                        ctx.auth = read_string(SLOT_NAME_ADDR, 0x40)
                        logger.info("auth is:" + str(ctx.auth))
                    if ctx.awaiting_rom:
                        await ctx.server_auth()
                sleep_time = 0.1
            else:
                if ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                    logger.info("Connection to Dolphin lost, reconnecting...")
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                logger.info("Attempting to connect to Dolphin...")
                dolphin_memory_engine.hook()
                if dolphin_memory_engine.is_hooked():
                    if dolphin_memory_engine.read_bytes(0x80000000, 6) != b"GR2E52":
                        logger.info(dolphin_memory_engine.read_bytes(0x80000000, 6))
                        logger.info(CONNECTION_REFUSED_GAME_STATUS)
                        ctx.dolphin_status = CONNECTION_REFUSED_GAME_STATUS
                        dolphin_memory_engine.un_hook()
                        sleep_time = 5
                    else:
                        logger.info(CONNECTION_CONNECTED_STATUS)
                        ctx.dolphin_status = CONNECTION_CONNECTED_STATUS
                        ctx.locations_checked = set()
                else:
                    logger.info("Connection to Dolphin failed, attempting again in 5 seconds...")
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                    await ctx.disconnect()
                    sleep_time = 5
                    continue
        except Exception:
            dolphin_memory_engine.un_hook()
            logger.info("Connection to Dolphin failed, attempting again in 5 seconds...")
            logger.error(traceback.format_exc())
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            await ctx.disconnect()
            sleep_time = 5
            continue


def main(*launch_args: str):
    from .client.dolphin_launcher import DolphinLauncher
    import colorama

    server_address: str = ""
    rom_path: str = ""

    Utils.init_logging(CLIENT_NAME)
    logger.info(f"Starting LK2 Client {CLIENT_VERSION}")
    dolphin_launcher: DolphinLauncher = DolphinLauncher()

    parser = get_base_parser()
    parser.add_argument('aplm_file', default="", type=str, nargs="?", help='Path to an APLM file')
    parser.add_argument('--name', default=None, help="Slot Name to connect as.")
    args = parser.parse_args(launch_args)
    logger.info("Launch args: " + str(launch_args))

    lk2_usa_manifest = None
    if args.aplm_file:
        lk2_usa_patch = LK2USAAPPatch()
        try:
            lk2_usa_manifest = lk2_usa_patch.read_contents(args.aplm_file)
            server_address = lk2_usa_manifest["server"]
            rom_path= lk2_usa_patch.patch(args.aplm_file)
        except Exception as ex:
            err_msg: str = f"Unable to patch your Lost Kingdoms 2 ROM as expected.\n" + \
                f"APWorld Version: '{CLIENT_VERSION}'\nAdditional details:{str(ex)}"
            logger.error(err_msg)
            Utils.messagebox("Cannot Lost Kingdoms 2", err_msg, True)
            raise ex

    async def _main(connect, password):

        ctx = LK2Context(server_address if server_address else connect, password)

        logger.info("Creating Server Loop")
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")

        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        await asyncio.sleep(1)

        ctx.dolphin_sync_task = asyncio.create_task(dolphin_sync_task_main_task(ctx), name="DolphinSync")

        await ctx.exit_event.wait()

        #ctx.watcher_event.set()
        #ctx.server_address = None

        await ctx.shutdown()

        if ctx.dolphin_sync_task:
            await ctx.dolphin_sync_task

    Utils.asyncio.run(dolphin_launcher.launch_dolphin_async(rom_path))

    colorama.just_fix_windows_console()
    asyncio.run(_main(args.connect, args.password))
    colorama.deinit()

if __name__ == "__main__":
    Utils.init_logging(CLIENT_NAME, exception_logger="Client")
    main(*sys.argv[1:])

