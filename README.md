# Lost Kingdoms II Archipelago

An [Archipelago](https://archipelago.gg) randomizer world for **Lost Kingdoms II** (Nintendo GameCube).

Cards, levels, shops, enemies and more are shuffled into the multiworld. Items you find go to
other players' games, and your own progression arrives from theirs.

---

## What you need:

| | |
|---|---|
| **Archipelago** | 0.5.0 or newer [releases](https://github.com/ArchipelagoMW/Archipelago/releases) |
| **Dolphin** | 5.0-19870 or newer [dolphin-emu.org](https://dolphin-emu.org/download/) |
| **A game disc image** | `Lost Kingdoms II (USA)`, GameCube, unmodified `.iso` |
| **This APWorld** | `lost_kingdoms_2.apworld` from [Releases](../../releases) |

Your disc image must be a **full, untrimmed dump of the USA release**. The patcher writes into
padding past the end of the file system, and refuses to run on a trimmed or scrubbed image rather
than producing a broken game. PAL and JP discs are not supported — the patches use USA memory
addresses throughout.

> This project does not distribute game files. You must supply your own disc image, dumped from a
> disc you own.

---

## Installation

1. Install Archipelago.
2. Double-click `lost_kingdoms_2.apworld`. It installs into your Archipelago `custom_worlds` folder.
   If that does not work, copy it there yourself:
   - **Windows**  `%localappdata%\Archipelago\custom_worlds\`
   - **Linux**  `~/Archipelago/custom_worlds/`
   - **macOS**  `~/Library/Application Support/Archipelago/custom_worlds/`
3. Restart the Archipelago Launcher.

---

## Generating a game

1. In the Archipelago Launcher, click **Generate Template Options**. This writes
   `Lost Kingdoms 2.yaml` into your `Players/Templates` folder.
2. Copy it into `Players/`, open it in a text editor, set your name, and choose your options
   (see [Options](#options)). 
   Alternatively, you can use the "Options Creator" in the Archipelago Launcher.
3. Click **Generate**. The output lands in `output/` as a `.zip`.
4. Upload the `.zip` to [the Archipelago website](https://archipelago.gg/uploads) to host, or host
   it locally by searching for "Host" in the Archipelago Launcher and selecting your `.zip` file when prompted.
5. When hosting on the Archipelago website, the generated room should contain a link to download the patch file
   for Lost Kingdoms 2. Download it. It should be a .aplk2 file.
6. If hosting locally, the .aplk2 file should be in the generated .zip folder. Copy and paste it from this folder.

For a solo game you can skip hosting and generate on your own machine.

---

## Patching your disc image

1. In the Archipelago Launcher, click **Open Patch**.
2. Select the `.aplk2` file from your generated seed.
3. When prompted, select your `Lost Kingdoms II (USA).iso` and your `Dolphin.exe`.

The patcher writes a new `.iso` to wherever your .aplk2 file is located. **Your original file is not modified**; keep
it, since every new seed patches from a clean copy.

Patching may take up to a minute, and will automatically open your Dolphin and the Lost Kingdoms 2 Launcher.

---

## Playing

1. Open your patched `.iso` in Dolphin and start the game if it did not open automatically.
2. In the Archipelago Launcher, click **Lost Kingdoms 2 Client** if it did not open automatically.
3. Enter the server address, your slot name, and the password if the host set one. This typically comes in the form of SlotName:Password@HostName:Port;
   for example, if you are hosting locally it may look like `Cokeman5:None@localhost:38281`. The player name is set in the .yaml file
4. Click `Connect`
5. The client finds Dolphin automatically once the game is running. If it does not, you should get a message indicating it is waiting on the connection to Dolphin.

The client must stay open while you play — it is what sends your checks and delivers your items.

**Save often.** Items you receive are written into the game's save data, so anything collected
since your last save is re-delivered on load rather than lost, but saving keeps the two in step.

---

## What does this randomize?

### Randomization Options

- Starting Deck(Optional)
- Shop Contents(Optional)
- Bonus Rewards(Optional)
- Shop Prices(Optional)
- Copy XP Costs(Optional)
- Upgrade XP Costs(Optional)
- Magic Stone Costs(Optional)
- Music(Optional)
- Player Model(Optional)
- Level Unlocks(Optional)

### Items

- Cards
- Key items
- Level Unlocks(Optional)
- Character levels(Optional)
- Attribute Proficiencies(Optional)

### Locations

- Chests & other card rewards
- Key item pickups throughout the levels
- Red Fairies(Optional)
- Enemysanity(Optional)
- Combosanity(Optional)

### Other

- Deathlink

All the optional options can be switched on or off, and many can be weighted, in your `.yaml`. The template
that Archipelago generates lists every option with its own explanation and default. 
Typically `50` means enabled, and `0` means disabled.

---

## Troubleshooting

**"Unable to patch your Lost Kingdoms 2 ROM as expected"**
Usually a disc image that is not an unmodified USA dump. Check the region, and check the file has
not been trimmed or scrubbed. The message ends with a short detail naming what failed.

**The client will not connect to Dolphin**
Start the game first, then the client. Make sure the game is actually running rather than paused at
the emulator's menu, and that you opened the *patched* image.

**The client connects but nothing happens**
Confirm the slot name in the client exactly matches the one in your `.yaml`, including case.

**Enemies have wrong or corrupted textures**
Make sure you are on the latest release. If it persists on a fresh patch, please open an issue with
your seed number and the level where you saw it.

**Items arrive but disappear after a reset**
Save in-game after receiving items. Anything since your last save is re-sent on connect, so nothing
should be permanently lost.

---

## Reporting issues

Bug reports and questions go to the **Archipelago Discord** — find the **Lost Kingdoms 2** thread in
the **#future-game-design** channel.

[Join the Archipelago Discord](https://discord.gg/8Z65BR2)

Logs from the Archipelago client help a great deal. They are in your Archipelago `logs/` folder.

---

## Credits

- PapayaJordane on Github for his Lost Kingdoms 2 Randomizer, for which this APworld got its start.(https://github.com/PapayaJordane/Lost-Kingdoms-2-Randomizer)
- culk on Discord/Github who has created a wonderful Poptracker for this APworld (https://github.com/culk/lost-kingdoms-2-poptracker-pack) and frequently reports bugs to me.
- Flamjam on Discord who created the AP Card art seen in the LK2 Apworld.
- Built on [Archipelago](https://archipelago.gg).

Thanks to everyone who has tested seeds and reported bugs. A great deal of this was found by
players noticing something was off and being specific about it.

## AI Disclaimer
- Lost Kingdoms 2 Archipelago is **partially** coded with the help of AI
- Lost Kingdoms 2 Archipelago does **not** contain AI art
- AI helps me with making tweaks to the games that would otherwise be infeasible due to the complexity of fully compiled gamecube era code.
- AI is almost exclusively used for understanding the game's code, and adding features that require tweaking the game's code at the PowerPC level, rather than the AP side of the code.