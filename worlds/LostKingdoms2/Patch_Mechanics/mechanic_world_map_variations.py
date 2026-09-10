"""
Give every world map level a submenu with two entries.

Every level in the game has a pre-completion and a post-completion variation.
This turns each level's single map icon into a submenu holding two entries -
"<Level Name> 1" and "<Level Name> 2" - so a player can pick which one to
enter. Both entries currently enter the same level; choosing the variation
is a separate problem this mechanic does not touch.

The world map tree
------------------
The map is a tree of 16-byte nodes in lists terminated by 0xFF:

    +0   type    0 = leaf (enters a level), 1 = submenu, 2 = area transition
    +1   index   leaf: level id | branch: slot in the child-list table
    +2   u16     icon id, passed to DrawWorldMapIcon
    +4   u16     x
    +6   u16     y
    +8   u16     width
    +10  u16     height
    +12  u8      leaf: the level id again | branch: its first child's level id
    +13  s8      label Y offset
    +14  u8      fade alpha - WRITTEN EVERY FRAME by the game
    +15  u8      unused in vanilla (0 in all 59 nodes) - we store the
                 variation number here, which is what lets the name stub
                 tell entry 1 from entry 2

Branches find their children through a pointer table, indexed by the branch's
own index byte:  children = CHILD_LIST_TABLE[node[1] * 4]

Why the table has to move
-------------------------
The vanilla table holds 11 entries; slots 1-10 are used and code pointers
begin immediately after it, so it cannot grow in place. Each converted level
needs its own slot, so the table is rebuilt in the code cave with room for
the new slots and all 23 instruction pairs that build its address are
repointed. Nothing is shifted: the original table is simply abandoned.

Where the names come from
-------------------------
Names are NOT in the map tables. FUN_800a80f4 looks them up in text tables
loaded from game/menu:

    type 1 (submenu)  ->  GetUIText(3, node[1])   keyed by SLOT
    type 0 (leaf)     ->  GetUIText(0, node[1])   keyed by LEVEL ID

That is why a converted node renders blank: our slots have no category-3
entry, GetUIText returns null, and the null reaches sprintf's %s handler.
Rather than add text assets, two calls are redirected to stubs:

  * branch: try GetUIText(3, slot); on null fall back to
    GetUIText(0, node[12]), which is the level's own name. Vanilla branches
    keep their own names, because the fallback only fires where there was
    nothing to begin with.
  * leaf: after GetUIText(0, level), if node[15] is set, format
    "<name> <n>" into a scratch buffer. The game already does exactly this
    for area nodes, using a static buffer consumed before the next node is
    drawn.

Levels 50-69 are omitted: they are the Proving Grounds, entered through a
single icon and transitioned between inside the level, with no
pre/post distinction to choose between.
"""
import logging
import struct

from worlds.LostKingdoms2.LK2Client import STORAGE_ADDRESSES

logger = logging.getLogger("Lost Kingdoms 2")

CHILD_LIST_TABLE = 0x80167650
VANILLA_SLOT_COUNT = 11

GET_UI_TEXT = 0x8004A474
SPRINTF = 0x8011B090

# FUN_800a80f4 contains TWO copies of the same label lookup - one per drawing
# path - and both must be redirected. Patching only the first left every node
# drawn through the second path with a vanilla label: blank for our submenus
# (their slot has no category-3 name) and unnumbered for our extra leaves.
#
# In both copies r29 holds the node pointer and the result lands in r27, so
# the same pair of stubs serves all four call sites.
# The label lookup appears THREE times in the map code, once per drawing
# path, and they do not agree on where the node pointer lives:
#
#   block 1 and 2  the node is in r29
#   block 3        the node is reloaded from a struct field, r30 + 768 + 28,
#                  because r3 (which held it) is overwritten with the table id
#                  before the call
#
# Patching only the r29 blocks left block 3 on the vanilla lookup, which is
# why no label was ever numbered - that block draws the labels you actually
# see. Each site is listed with the instruction that recovers its node.
NODE_FROM_R29 = "r29"
NODE_FROM_STRUCT = "struct"

LEAF_TEXT_CALLS = (
    (0x800A83F4, NODE_FROM_R29),
    (0x800A879C, NODE_FROM_R29),
    (0x800A90E8, NODE_FROM_STRUCT),
)
BRANCH_TEXT_CALLS = (
    (0x800A841C, NODE_FROM_R29),
    (0x800A87C4, NODE_FROM_R29),
    (0x800A9110, NODE_FROM_STRUCT),
)

# r30 + 768 + 28: the selected node, as block 3 itself loads it
NODE_STRUCT_OFFSET = 768 + 28

# --- entering a level as beaten or not beaten ------------------------------
#
# Level progress lives in 90 records of 0x40 bytes based at
# LEVEL_RECORD_BASE. The completion flag is the first byte of a record:
#     flag = LEVEL_RECORD_BASE + level_id * 0x40      (1 = beaten)
# The map's own reset loop confirms the shape - it runs
# (&DAT_8025dbce)[i * 0x40] &= 0xdf for i < 0x5a, where 0x8025dbce is +2 of
# the same record.
#
# Entry 1 clears the flag and entry 2 sets it, so the level loads in its
# before or after state. The flag is simply left that way: it now reflects
# what was actually played, and nothing in the randomizer's logic depends on
# level completion.
#
# The write happens where the map opens its confirm prompt for a level.
# Three calls to InitDialogueBoxMessage sit in that function and two of them
# set worldMapConfirmState = 2; rather than guess which is the leaf branch,
# the stub re-reads selectedWorldMapNode and does nothing unless it is a leaf
# carrying a variation number. That makes patching every candidate safe.
LEVEL_RECORD_BASE = 0x8025DBCC
LEVEL_RECORD_STRIDE = 0x40
SELECTED_NODE_POINTER = 0x80286E34   # highlighted node on the map itself
SUBMENU_SELECTED_NODE = 0x80286E3C   # highlighted node inside an open submenu
INIT_DIALOGUE_BOX_MESSAGE = 0x8005F1B0
CONFIRM_PROMPT_CALLS = (0x800A719C, 0x800A7710, 0x800A8058)

# Diagnostic. When True the completion-flag stub writes 1 to
# DIAGNOSTIC_MARKER as its very first act, before looking at any node. That
# separates the two ways this can fail:
#
#   marker changes  -> the stub runs; the node pointers it checks are wrong
#   marker unchanged -> the stub never runs; the confirm call sites are wrong
#
# The marker is level 1's own completion flag, so confirming ANY level should
# mark Nobleman's Residence complete. Set back to False once diagnosed.
DIAGNOSTIC_ALWAYS_WRITE = False

# --- hiding the "beaten" entry until the level is actually beaten ----------
#
# Visibility is bit 7 of the record's +2 byte, keyed by LEVEL id - so both of
# our entries share it and are shown or hidden together. Entry 2 additionally
# requires the completion flag, which makes the decision per-NODE.
#
# The same test appears 14 times, but only three can see a submenu entry:
#
#   0x800A68C4  CheckWorldMapNodeVisible, the leaf case (node in r3)
#   0x800A7C84  UpdateWorldMapCursorSnap, cursor snap  (node in r5)
#   0x800A7D0C  UpdateWorldMapCursorSnap, cursor snap  (node in r5)
#
# The other eleven are CheckWorldMapNodeVisible's recursive scans of a
# branch's children - which only decide whether the BRANCH is drawn, and
# entry 1 keeps it visible either way - plus cursor paths whose node register
# is already dead by the test.
VISIBLE_BIT_LEAF_BLOCK = 0x800A68C4     # start of the leaf case, node still in r3
VISIBLE_BIT_LEAF_YES = 0x800A68E4       # li r3,1  - the "visible" exit
VISIBLE_BIT_LEAF_NO = 0x800A6D10        # the "hidden" exit
CURSOR_VISIBLE_TESTS = (0x800A7C84, 0x800A7D0C)
# A variation number above 1 is a "post-completion" entry and needs the level
# to have been beaten before it appears. Written as a threshold rather than
# "== 2" because a level can have more than two entries - see
# LEVEL_COMPLETION_VALUES below.
FIRST_POST_COMPLETION_VARIATION = 2

# The furthest each level has ever progressed - one BYTE per level, holding
# the highest value its completion flag has ever held:
#     LEVEL_PROGRESS + level
#
# The vanilla flag at record+0x00 cannot serve this purpose, because entering
# an entry deliberately overwrites it: replaying part 1 would otherwise make
# the game forget the level had been finished at all.
#
# A byte rather than a bit, because a level can have several stages. Bhashea
# High Road runs 0 -> 2 -> 3, and entry 3 must require 3, not merely "beaten".
# A single bit could not express that.
#
# This only ever increases. It lives in STORAGE_ADDRESSES, inside the unused
# records past the last real level, and is saved with the rest of the array.
if 'level_progress' not in STORAGE_ADDRESSES:
    raise KeyError(
        "STORAGE_ADDRESSES has no 'level_progress' entry. This mechanic used to "
        "use a 12-byte 'level_completion' bitmask; it now needs one BYTE per "
        "level, because a bit cannot tell 'finished part 1' from 'finished "
        "part 2' and multi-part levels unlock in sequence. Replace the old "
        "entry in LK2Client.py with:\n"
        "    'level_progress': {'address': 0x8025ed90, 'size': 90},"
    )

LEVEL_PROGRESS = STORAGE_ADDRESSES['level_progress']['address']
LEVEL_PROGRESS_SIZE = STORAGE_ADDRESSES['level_progress']['size']

assert LEVEL_PROGRESS_SIZE >= 90, (
    f"level_progress is {LEVEL_PROGRESS_SIZE} bytes; 90 are needed, one per "
    f"level record"
)

DIAGNOSTIC_MARKER = 0x8025DC0C

# The title drawn at the top of an OPEN submenu - "Alanjeh", "Runestone
# Caverns" and so on. This is a separate lookup from the icon labels: it is
# keyed by the slot number held at +3 of a UI state struct in r28, not by any
# node, so the stubs above never see it. Vanilla slots 5-10 have a category-3
# title; ours do not, which is what was still producing a null %s.
# There are TWO of these, reading the slot from different places, and both
# feed a render call that formats the result with %s - so a null from either
# is the crash. Listed as (call site, base register, offset).
SUBMENU_TITLE_CALLS = (
    (0x800A8C4C, 28, 3),   # lbz r4,3(r28)
    (0x800A9260, 25, 4),   # lbz r4,4(r25)
)

NODE_SIZE = 16
LIST_TERMINATOR = 0xFF
NODE_TYPE_LEAF = 0
NODE_TYPE_SUBMENU = 1

# Proving Grounds. One icon enters level 50 and the other 19 are reached from
# inside it, so there is no completed/not-completed choice to offer.
OMITTED_LEVELS = range(50, 70)

# Levels that already live inside a submenu and DO want a second entry.
# These get an extra leaf added beside the original in their existing parent
# list - not a submenu of their own, which would bury them a level deeper for
# no reason.
#
#    5  Runestone Caverns - Upper Chambers  ) list[6]
#    6  Runestone Caverns - Lower Chambers  )
#   11  Alanjeh Castle       )
#   12  Royal Tower, Lower   ) list[8]
#   15  Royal Tower, Middle  )
#
# Everything else inside a submenu is left alone:
#    3  Kadishu                  )
#   40  Fairy House              ) list[5]
#   41  Kadishu Shop             )
#   23  Sacred Battle Arena 1    ) list[7]
#   24  Sacred Battle Arena 2    )
#   16  Royal Tower, Upper       - nothing changes after beating it
#   14  Grenfoel Cathedral       ) list[9]
#   42  Grenfoel Cathedral Shop  )
#
# The level ids here were confirmed against the game rather than inferred
# from the tree's shape - two earlier guesses from structure alone (that
# list[7] was the Runestone Caverns, and that level 14 was Alanjeh Castle)
# were both wrong.
SUBMENU_DUPLICATE_LEVELS = frozenset({5, 6, 11, 12, 15})

# A duplicate sits directly below its original rather than beside it. The
# parent lists are already laid out as a single row with ~60px spacing, so
# inserting entries in that row would overlap the neighbours.
DUPLICATE_Y_OFFSET = 50

# Where the two entries sit inside the submenu, copied from the Kadishu Shop /
# Fairy House pair so they land where the game already draws a two-entry
# submenu rather than somewhere untested.
# Screen positions per entry count, copied from the vanilla submenus that
# already use that many icons rather than derived. Every vanilla layout is
# centred near x=296; spacing narrows as entries are added so they stay inside
# the panel. An earlier hand-made 3-entry layout simply extended the 2-entry
# spacing and pushed the third icon off the edge of the panel, where the
# cursor could not reach it either.
#
#   2 entries - list[6], Kadishu Shop / Fairy House
#   3 entries - list[5], Kadishu / Sacred Battle Arena 1 / 2
#   4 entries - list[8], Alanjeh Castle / Royal Tower x3
ENTRY_LAYOUTS = {
    2: (
        {"x": 247, "y": 227, "w": 46, "h": 46},
        {"x": 348, "y": 228, "w": 44, "h": 44},
    ),
    3: (
        {"x": 216, "y": 226, "w": 48, "h": 48},
        {"x": 295, "y": 225, "w": 50, "h": 50},
        {"x": 375, "y": 225, "w": 50, "h": 50},
    ),
    4: (
        {"x": 206, "y": 224, "w": 48, "h": 48},
        {"x": 266, "y": 226, "w": 48, "h": 48},
        {"x": 326, "y": 226, "w": 48, "h": 48},
        {"x": 386, "y": 221, "w": 48, "h": 48},
    ),
}
# What each entry writes into the level's completion byte (record + 0x00) on
# the way in. This is NOT simply "0 for unbeaten, 1 for beaten": the byte is a
# per-level progress value, and a level with several parts uses several
# values.
#
# Bhashea High Road (level 2) has three, using the game's own progression
# values for that level.
#
# These values double as the UNLOCK condition. An entry appears once the level
# has ever reached that value, so entry 3 needs the player to have beaten
# entry 2 - not merely to have beaten the level once. That is why the progress
# store below keeps a value per level rather than a single "beaten" bit: a bit
# cannot tell "finished part 1" from "finished part 2".
#
# Any level not listed gets the ordinary two entries.
DEFAULT_COMPLETION_VALUES = (0, 1)
LEVEL_COMPLETION_VALUES = {
    2: (0, 2, 3),   # Bhashea High Road: part 1 unbeaten, part 1 beaten, part 2
}

# The progress table spans more than one record, so one record's +2 byte falls
# inside it, and the game's map-reset loop masks every such byte with 0xDF.
# That clears bit 5 only, so any value below 0x20 survives untouched. No
# contiguous 90-byte span can dodge every +2 (records are 0x40 apart and only
# 63 bytes separate consecutive +2 bytes), so this is asserted rather than
# designed around.
assert all(
    value < 0x20
    for values in list(LEVEL_COMPLETION_VALUES.values()) + [DEFAULT_COMPLETION_VALUES]
    for value in values
), "a completion value >= 0x20 would be corrupted by the game's map-reset loop"

NAME_FORMAT = b"%s %d\x00"
NAME_BUFFER_SIZE = 64


def _read_node(patcher, ram_address):
    patcher.file.seek(patcher.ram_to_iso(ram_address))
    return patcher.file.read(NODE_SIZE)


def _read_word(patcher, ram_address):
    patcher.file.seek(patcher.ram_to_iso(ram_address))
    return struct.unpack(">I", patcher.file.read(4))[0]


def _submenu_slots(patcher):
    """Slots reached by a type-1 branch, i.e. lists that are already submenus.

    Levels inside these do not become submenus of their own; they get an extra
    leaf added to the list they are already in.
    """
    slots = set()
    for slot in range(1, VANILLA_SLOT_COUNT):
        address = _read_word(patcher, CHILD_LIST_TABLE + slot * 4)
        for _ in range(64):
            node = _read_node(patcher, address)
            if node[0] == LIST_TERMINATOR:
                break
            if node[0] == NODE_TYPE_SUBMENU:
                slots.add(node[1])
            address += NODE_SIZE
    return slots


def _walk_tree(patcher):
    """Every leaf node in the map, as (list_slot, node_address, level_id)."""
    leaves = []
    for slot in range(1, VANILLA_SLOT_COUNT):
        list_address = _read_word(patcher, CHILD_LIST_TABLE + slot * 4)
        if not (0x80000000 <= list_address < 0x81800000):
            raise ValueError(
                f"Child list slot {slot} holds {hex(list_address)}, which is not "
                f"a RAM address. The map tree is not laid out as expected."
            )
        address = list_address
        for _ in range(64):  # generous bound; real lists are far shorter
            node = _read_node(patcher, address)
            if node[0] == LIST_TERMINATOR:
                break
            if node[0] == NODE_TYPE_LEAF:
                leaves.append((slot, address, node[1]))
            address += NODE_SIZE
        else:
            raise ValueError(f"Child list {slot} has no terminator - refusing to continue")
    return leaves


def apply(patcher, output_data=None):
    submenu_slots = _submenu_slots(patcher)
    all_leaves = _walk_tree(patcher)

    # Top-level levels: a level with no submenu of its own gets one, holding
    # two entries.
    to_convert = [
        (slot, address, level_id)
        for slot, address, level_id in all_leaves
        if slot not in submenu_slots and level_id not in OMITTED_LEVELS
    ]
    # Levels already inside a submenu: the parent list gains a second leaf
    # beside the original instead.
    slots_to_extend = sorted({
        slot for slot, _, level_id in all_leaves
        if slot in submenu_slots and level_id in SUBMENU_DUPLICATE_LEVELS
    })
    if not to_convert and not slots_to_extend:
        raise ValueError("No convertible level nodes found in the world map tree")

    # --- the relocated, extended child-list table ---------------------------
    total_slots = VANILLA_SLOT_COUNT + len(to_convert)
    table_address = patcher.alloc_cave(total_slots * 4)
    for slot in range(VANILLA_SLOT_COUNT):
        patcher.patch_word(table_address + slot * 4,
                           _read_word(patcher, CHILD_LIST_TABLE + slot * 4))

    # --- a submenu for each top-level level ---------------------------------
    for offset, (_, node_address, level_id) in enumerate(to_convert):
        slot = VANILLA_SLOT_COUNT + offset
        original = _read_node(patcher, node_address)
        icon_id = struct.unpack_from(">H", original, 2)[0]

        values = LEVEL_COMPLETION_VALUES.get(level_id, DEFAULT_COMPLETION_VALUES)
        if len(values) not in ENTRY_LAYOUTS:
            raise ValueError(
                f"level {level_id} wants {len(values)} entries, but no screen "
                f"layout is defined for that many. ENTRY_LAYOUTS has "
                f"{sorted(ENTRY_LAYOUTS)}; copy the positions from a vanilla "
                f"submenu with the same number of icons."
            )
        layouts = ENTRY_LAYOUTS[len(values)]

        entries = b""
        for number, (layout, completion_value) in enumerate(
                zip(layouts, values), start=1):
            entries += struct.pack(
                ">BBHHHHHBBBB",
                NODE_TYPE_LEAF, level_id, icon_id,
                layout["x"], layout["y"], layout["w"], layout["h"],
                # +12 carries the completion value this entry writes. Vanilla
                # submenu leaves hold 0 here and nothing reads it on a leaf,
                # so it is ours to use - and keeping it per-node means the
                # stub needs no table lookup.
                completion_value,
                0, 0, number,
            )
        entries += bytes([LIST_TERMINATOR]) + b"\x00" * (NODE_SIZE - 1)

        list_address = patcher.alloc_cave(len(entries))
        patcher.patch_bytes(list_address, entries)
        patcher.patch_word(table_address + slot * 4, list_address)

        converted = bytearray(original)
        converted[0] = NODE_TYPE_SUBMENU
        converted[1] = slot
        converted[12] = level_id
        patcher.patch_bytes(node_address, bytes(converted))

    # --- extra leaves inside existing submenus ------------------------------
    for slot in slots_to_extend:
        _extend_submenu(patcher, slot, table_address)

    _repoint_table_references(patcher, table_address)
    _install_name_stubs(patcher, [level_id for _, _, level_id in to_convert])

    logger.info(
        f"[mechanic_world_map_variations] {len(to_convert)} level(s) given a "
        f"submenu, {len(slots_to_extend)} existing submenu(s) extended; "
        f"child-list table moved to {hex(table_address)} with {total_slots} slots"
    )


def _extend_submenu(patcher, slot, table_address):
    """Rebuild one existing submenu list with a duplicate of each wanted level.

    The vanilla lists sit in read-only data with code immediately after, so a
    list cannot grow where it is. It is rebuilt in the cave instead and the
    table slot repointed - which is cheap now that the table is ours.

    Each duplicated level keeps its original entry (numbered 1) and gains a
    second directly below it (numbered 2). Levels in the list that are not
    being duplicated are copied across untouched, including their variation
    byte, so they keep their plain unnumbered name.
    """
    address = _read_word(patcher, CHILD_LIST_TABLE + slot * 4)
    rebuilt = b""
    duplicated = []

    for _ in range(64):
        node = _read_node(patcher, address)
        if node[0] == LIST_TERMINATOR:
            break
        if node[0] == NODE_TYPE_LEAF and node[1] in SUBMENU_DUPLICATE_LEVELS:
            values = LEVEL_COMPLETION_VALUES.get(node[1], DEFAULT_COMPLETION_VALUES)
            assert len(values) == 2, (
                f"level {node[1]} lives inside an existing submenu, which has "
                f"room for one duplicate only, but {len(values)} entries are "
                f"configured for it"
            )

            first = bytearray(node)
            first[12] = values[0]      # the value this entry writes on entry
            first[15] = 1
            rebuilt += bytes(first)

            second = bytearray(node)
            second[12] = values[1]
            second[15] = 2
            y = struct.unpack_from(">H", node, 6)[0] + DUPLICATE_Y_OFFSET
            struct.pack_into(">H", second, 6, y)
            rebuilt += bytes(second)
            duplicated.append(node[1])
        else:
            rebuilt += bytes(node)
        address += NODE_SIZE

    rebuilt += bytes([LIST_TERMINATOR]) + b"\x00" * (NODE_SIZE - 1)

    list_address = patcher.alloc_cave(len(rebuilt))
    patcher.patch_bytes(list_address, rebuilt)
    patcher.patch_word(table_address + slot * 4, list_address)
    logger.info(
        f"[mechanic_world_map_variations] submenu slot {slot} rebuilt at "
        f"{hex(list_address)}, duplicated level(s) {duplicated}"
    )


def _repoint_table_references(patcher, new_address):
    """Rewrite the lis/addi pairs that build CHILD_LIST_TABLE.

    Every reference in the DOL is a `lis rD, hi` followed within a few
    instructions by `addi rD, rD, lo`. Both halves are rewritten in place, so
    no code moves. The pairs are located by scanning rather than hardcoded, so
    a miscount cannot silently leave one behind pointing at the old table.
    """
    if new_address & 0xFFFF >= 0x8000:
        # addi sign-extends its immediate; the cave sits low enough that this
        # never happens, but a silent off-by-0x10000 would be miserable.
        raise ValueError(
            f"New table at {hex(new_address)} has a low half >= 0x8000, which "
            f"addi would sign-extend. Adjust the allocation."
        )
    high, low = (new_address >> 16) & 0xFFFF, new_address & 0xFFFF

    patched = 0
    for lis_address, addi_address in _find_table_references(patcher):
        patcher.file.seek(patcher.ram_to_iso(lis_address))
        lis = struct.unpack(">I", patcher.file.read(4))[0]
        patcher.patch_word(lis_address, (lis & 0xFFFF0000) | high)

        patcher.file.seek(patcher.ram_to_iso(addi_address))
        addi = struct.unpack(">I", patcher.file.read(4))[0]
        patcher.patch_word(addi_address, (addi & 0xFFFF0000) | low)
        patched += 1

    if patched == 0:
        raise ValueError("Found no references to the child-list table to repoint")
    logger.info(f"[mechanic_world_map_variations] repointed {patched} table reference(s)")


def _find_table_references(patcher):
    """Locate `lis rD, hi(TABLE)` + `addi rD, rD, lo(TABLE)` pairs in the DOL."""
    references = []
    start, end = 0x80003100, 0x8014DD00
    patcher.file.seek(patcher.ram_to_iso(start))
    text = patcher.file.read(end - start)

    for position in range(0, len(text) - 4, 4):
        word = struct.unpack_from(">I", text, position)[0]
        if (word >> 26) & 0x3F != 15:  # lis
            continue
        register, high = (word >> 21) & 0x1F, word & 0xFFFF
        for step in range(1, 8):
            following = position + step * 4
            if following + 4 > len(text):
                break
            word2 = struct.unpack_from(">I", text, following)[0]
            if (word2 >> 26) & 0x3F != 14:  # addi
                continue
            if (word2 >> 16) & 0x1F != register:
                continue
            low = word2 & 0xFFFF
            value = (high << 16) + (low - 0x10000 if low & 0x8000 else low)
            if value == CHILD_LIST_TABLE:
                references.append((start + position, start + following))
            break
    return references


# --- PowerPC encoders, only what the two stubs need ------------------------
def _lis(rD, value):        return (15 << 26) | (rD << 21) | (value & 0xFFFF)
def _ori(rA, rS, value):    return (24 << 26) | (rS << 21) | (rA << 16) | (value & 0xFFFF)
def _li(rD, value):         return (14 << 26) | (rD << 21) | (value & 0xFFFF)
def _addi(rD, rA, value):   return (14 << 26) | (rD << 21) | (rA << 16) | (value & 0xFFFF)
def _lbz(rD, offset, rA):   return (34 << 26) | (rD << 21) | (rA << 16) | (offset & 0xFFFF)
def _lwz(rD, offset, rA):   return (32 << 26) | (rD << 21) | (rA << 16) | (offset & 0xFFFF)
def _stw(rS, offset, rA):   return (36 << 26) | (rS << 21) | (rA << 16) | (offset & 0xFFFF)
def _stwu(rS, offset, rA):  return (37 << 26) | (rS << 21) | (rA << 16) | (offset & 0xFFFF)
def _mr(rA, rS):            return (31 << 26) | (rS << 21) | (rA << 16) | (rS << 11) | (444 << 1)
def _mflr(rD):              return (31 << 26) | (rD << 21) | (8 << 16) | (339 << 1)
def _mtlr(rS):              return (31 << 26) | (rS << 21) | (8 << 16) | (467 << 1)
def _cmplw(rA, rB):         return (31 << 26) | (rA << 16) | (rB << 11) | (32 << 1)


def _cmpwi(rA, value):      return (11 << 26) | (rA << 16) | (value & 0xFFFF)
def _blr():                 return 0x4E800020
def _lbzx(rD, rA, rB):      return (31 << 26) | (rD << 21) | (rA << 16) | (rB << 11) | (87 << 1)
def _stb(rS, offset, rA):   return (38 << 26) | (rS << 21) | (rA << 16) | (offset & 0xFFFF)
def _add(rD, rA, rB):       return (31 << 26) | (rD << 21) | (rA << 16) | (rB << 11) | (266 << 1)


def _rlwinm(rA, rS, sh, mb, me):
    return (21 << 26) | (rS << 21) | (rA << 16) | (sh << 11) | (mb << 6) | (me << 1)


def _ble(source, target):
    return 0x40810000 | ((target - source) & 0xFFFC)


def _blt(source, target):
    return 0x41800000 | ((target - source) & 0xFFFC)


def _b(source, target):
    return 0x48000000 | ((target - source) & 0x03FFFFFC)


def _slw(rA, rS, rB):       return (31 << 26) | (rS << 21) | (rA << 16) | (rB << 11) | (24 << 1)
def _or(rA, rS, rB):        return (31 << 26) | (rS << 21) | (rA << 16) | (rB << 11) | (444 << 1)
def _and(rA, rS, rB):       return (31 << 26) | (rS << 21) | (rA << 16) | (rB << 11) | (28 << 1)


def _bl(source, target):
    return 0x48000001 | ((target - source) & 0x03FFFFFC)


def _beq(source, target):
    return 0x41820000 | ((target - source) & 0xFFFC)


def _bne(source, target):
    return 0x40820000 | ((target - source) & 0xFFFC)


def _install_name_stubs(patcher, converted_levels):
    """Redirect the two label lookups in FUN_800a80f4 to stubs of our own.

    Both call sites have r29 = the node pointer and expect the string in r3.
    The stubs call GetUIText exactly as the original code did, then fix up the
    two cases the vanilla lookup cannot express:

      * a submenu slot with no category-3 name -> use the level's own name
      * a submenu entry carrying a variation number -> append that number

    Vanilla nodes hit neither case, so their labels come out unchanged.
    """
    name_format = patcher.alloc_cave(len(NAME_FORMAT))
    patcher.patch_bytes(name_format, NAME_FORMAT)
    name_buffer = patcher.alloc_cave(NAME_BUFFER_SIZE)
    patcher.patch_bytes(name_buffer, b"\x00" * NAME_BUFFER_SIZE)

    for variant in (NODE_FROM_R29, NODE_FROM_STRUCT):
        sites = [a for a, v in BRANCH_TEXT_CALLS if v == variant]
        _emit_branch_stub(patcher, variant, sites)
        sites = [a for a, v in LEAF_TEXT_CALLS if v == variant]
        _emit_leaf_stub(patcher, variant, sites, name_format, name_buffer)
    _emit_title_stubs(patcher, converted_levels)
    _emit_completion_flag_stub(patcher)
    _emit_visibility_stubs(patcher)


def _emit(patcher, instructions, labels=None):
    """Assemble a stub, resolving branch targets given as label names.

    An entry is one of:
        int                 a literal instruction
        ("bl", address)     a call to a fixed address
        ("beq", "name")     a branch to a label
        ("label", "name")   declares a label here; emits nothing

    Declaring labels inline means no instruction index is ever counted by
    hand, which is where two earlier branch targets went wrong - they landed
    on the second half of an address load instead of the epilogue.
    """
    resolved_labels = dict(labels or {})
    stream = []
    for instruction in instructions:
        if isinstance(instruction, tuple) and instruction[0] == "label":
            resolved_labels[instruction[1]] = len(stream)
        else:
            stream.append(instruction)

    address = patcher.alloc_cave(len(stream) * 4)
    for index, instruction in enumerate(stream):
        here = address + index * 4
        if isinstance(instruction, tuple):
            kind, target = instruction
            resolved = (address + resolved_labels[target] * 4) if isinstance(target, str) else target
            instruction = {"bl": _bl, "beq": _beq, "bne": _bne,
                           "blt": _blt, "ble": _ble, "b": _b}[kind](here, resolved)
        patcher.patch_word(here, instruction)
    return address


def _node_into(register, variant):
    """Instructions that put the node pointer into `register`."""
    if variant == NODE_FROM_R29:
        return [_mr(register, 29)]
    return [_lwz(register, NODE_STRUCT_OFFSET, 30)]


def _emit_branch_stub(patcher, variant, call_sites):
    """GetUIText(3, slot), falling back to GetUIText(0, node[12])."""
    labels = {"keep": 8, "done": 10}
    code = [
        _stwu(1, -16, 1),
        _mflr(0),
        _stw(0, 20, 1),
        ("bl", GET_UI_TEXT),          # the call this stub replaced
        _cmpwi(3, 0),
        ("bne", "keep"),              # slot has a real name - use it
        _li(3, 0),                    # else look the level's own name up
    ] + _node_into(7, variant) + [
        _lbz(4, 12, 7),               # node[12] = this submenu's level id
        # "keep" lands here for the vanilla path; the fallback falls through
        ("bl", GET_UI_TEXT),
        _lwz(0, 20, 1),
        _mtlr(0),
        _addi(1, 1, 16),
        _blr(),
    ]
    # The fallback must skip the second call when the first succeeded, so
    # "keep" points past it. Recompute the labels against the real layout.
    labels = {"keep": 9 + len(_node_into(7, variant))}
    code[5] = ("bne", "keep")
    address = _emit(patcher, code, labels)
    for call_site in call_sites:
        patcher.patch_word(call_site, _bl(call_site, address))
    logger.info(
        f"[mechanic_world_map_variations] branch name stub at {hex(address)}, "
        f"reached from {len(BRANCH_TEXT_CALLS)} call site(s)"
    )
    return address


def _emit_leaf_stub(patcher, variant, call_sites, name_format, name_buffer):
    """GetUIText(0, level), then append node[15] when it is set."""
    code = [
        _stwu(1, -32, 1),
        _mflr(0),
        _stw(0, 36, 1),
        _stw(31, 8, 1),               # borrow r31 - r30 is the struct base
        ("bl", GET_UI_TEXT),
        _mr(31, 3),                   # keep the name across sprintf
    ] + _node_into(7, variant) + [
        _lbz(4, 15, 7),               # variation number; 0 on vanilla nodes
        _cmpwi(4, 0),
        ("beq", "plain"),
        _lis(3, (name_buffer >> 16) & 0xFFFF),
        _ori(3, 3, name_buffer & 0xFFFF),
        _lis(4, (name_format >> 16) & 0xFFFF),
        _ori(4, 4, name_format & 0xFFFF),
        _mr(5, 31),                   # sprintf(buffer, "%s %d", name, number)
    ] + _node_into(6, variant) + [
        _lbz(6, 15, 6),
        ("bl", SPRINTF),
        _lis(3, (name_buffer >> 16) & 0xFFFF),
        _ori(3, 3, name_buffer & 0xFFFF),
        # "plain" lands here with the unmodified name still in r3
        _lwz(31, 8, 1),
        _lwz(0, 36, 1),
        _mtlr(0),
        _addi(1, 1, 32),
        _blr(),
    ]
    n = len(_node_into(7, variant))
    labels = {"plain": 18 + 2 * n}
    address = _emit(patcher, code, labels)
    for call_site in call_sites:
        patcher.patch_word(call_site, _bl(call_site, address))
    logger.info(
        f"[mechanic_world_map_variations] leaf name stub at {hex(address)}, "
        f"reached from {len(LEAF_TEXT_CALLS)} call site(s), "
        f"format {hex(name_format)}, buffer {hex(name_buffer)}"
    )
    return address


def _emit_title_stubs(patcher, converted_levels):
    """One stub per title lookup, sharing a single slot -> level id table."""
    table = patcher.alloc_cave(len(converted_levels))
    patcher.patch_bytes(table, bytes(converted_levels))
    for call_site, register, offset in SUBMENU_TITLE_CALLS:
        _emit_title_stub(patcher, table, len(converted_levels),
                         call_site, register, offset)


def _emit_title_stub(patcher, table, entry_count, call_site, register, offset):
    """Give an open submenu a title when its slot has no category-3 entry.

    The vanilla titles ("Alanjeh", "Runestone Caverns") are static strings
    keyed by slot, and our new slots have none - so this falls back to the
    level's own name, the same text the submenu's button shows.

    The slot is not a node here, so there is no +12 byte to read the level
    from. A slot -> level id table is emitted instead, covering only the slots
    this mechanic created; vanilla slots take the early exit and keep their
    own titles.
    """
    code = [
        _stwu(1, -16, 1),
        _mflr(0),
        _stw(0, 20, 1),
        ("bl", GET_UI_TEXT),           # the call this stub replaced
        _cmpwi(3, 0),
        ("bne", "done"),               # vanilla slot - it has a real title
        _lbz(4, offset, register),     # re-read the slot; r4 died in the call
        _cmpwi(4, VANILLA_SLOT_COUNT),
        ("blt", "done"),               # not one of ours, and still no title
        _addi(4, 4, -VANILLA_SLOT_COUNT),
        _lis(5, (table >> 16) & 0xFFFF),
        _ori(5, 5, table & 0xFFFF),
        _lbzx(4, 5, 4),                # level id for this slot
        _li(3, 0),                     # level name table
        ("bl", GET_UI_TEXT),
        _lwz(0, 20, 1),                # "done"
        _mtlr(0),
        _addi(1, 1, 16),
        _blr(),
    ]
    labels = {"done": 15}
    address = _emit(patcher, code, labels)
    patcher.patch_word(call_site, _bl(call_site, address))
    logger.info(
        f"[mechanic_world_map_variations] title stub at {hex(address)} for "
        f"{hex(call_site)} (slot from r{register}+{offset}), slot->level table "
        f"at {hex(table)} ({entry_count} entries)"
    )
    return address


def _emit_completion_flag_stub(patcher):
    """Set the level's completion flag to match the entry the player chose.

    Replaces the InitDialogueBoxMessage call that opens the confirm prompt.
    r3 and r4 are that function's arguments and are left untouched; only
    volatile scratch above r4 is used.

    The map tracks the highlighted entry in TWO different globals depending on
    how it was reached: selectedWorldMapNode for a level on the map itself,
    and SUBMENU_SELECTED_NODE for one inside an open submenu. The stub tries
    both and uses whichever is a leaf carrying a variation number, so it does
    not need to know which confirm path ran. That self-guarding also makes it
    safe to attach to every candidate call site.
    """
    def check(pointer, on_failure):
        return [
            _lis(5, (pointer >> 16) & 0xFFFF),
            _ori(5, 5, pointer & 0xFFFF),
            _lwz(5, 0, 5),                 # r5 = candidate node
            _cmpwi(5, 0),
            ("beq", on_failure),
            _lbz(0, 0, 5),                 # node type
            _cmpwi(0, NODE_TYPE_LEAF),
            ("bne", on_failure),
            _lbz(6, 15, 5),                # variation number
            _cmpwi(6, 0),
            ("bne", "apply"),
            ("beq", on_failure),
        ]

    code = [
        _stwu(1, -16, 1),
        _mflr(0),
        _stw(0, 20, 1),
    ]
    if DIAGNOSTIC_ALWAYS_WRITE:
        code += [
            _li(6, 1),
            _lis(7, (DIAGNOSTIC_MARKER >> 16) & 0xFFFF),
            _ori(7, 7, DIAGNOSTIC_MARKER & 0xFFFF),
            _stb(6, 0, 7),
        ]
        logger.warning(
            "[mechanic_world_map_variations] DIAGNOSTIC_ALWAYS_WRITE is on - "
            f"confirming any level will write 1 to {hex(DIAGNOSTIC_MARKER)}"
        )
    code += check(SELECTED_NODE_POINTER, "try_submenu")
    code += [("label", "try_submenu")]
    code += check(SUBMENU_SELECTED_NODE, "prompt")

    code += [
        ("label", "apply"),
        # node[12] holds the value this entry writes. Deriving it from the
        # variation number instead would assume "beaten == 1", which is wrong
        # for any level with more than one part.
        _lbz(6, 12, 5),
        _lbz(7, 1, 5),                 # level id
        _rlwinm(7, 7, 6, 0, 25),       # * 0x40, the record stride
        _lis(8, (LEVEL_RECORD_BASE >> 16) & 0xFFFF),
        _ori(8, 8, LEVEL_RECORD_BASE & 0xFFFF),
        _add(7, 8, 7),
        _stb(6, 0, 7),                 # completion flag = the chosen state

        ("label", "prompt"),
        ("bl", INIT_DIALOGUE_BOX_MESSAGE),   # the call we replaced
        _lwz(0, 20, 1),
        _mtlr(0),
        _addi(1, 1, 16),
        _blr(),
    ]
    address = _emit(patcher, code)
    for call_site in CONFIRM_PROMPT_CALLS:
        patcher.patch_word(call_site, _bl(call_site, address))
    logger.info(
        f"[mechanic_world_map_variations] completion flag stub at "
        f"{hex(address)}, attached to {len(CONFIRM_PROMPT_CALLS)} confirm site(s)"
    )
    return address


def _progress_address(level_register, out_register):
    """Instructions putting &LEVEL_PROGRESS[level] into out_register."""
    return [
        _lis(out_register, (LEVEL_PROGRESS >> 16) & 0xFFFF),
        _ori(out_register, out_register, LEVEL_PROGRESS & 0xFFFF),
        _add(out_register, out_register, level_register),
    ]


def _emit_visibility_stubs(patcher):
    """Show each entry only once the level has reached the value it needs.

    Entry 1 requires 0, so it is always available - the unbeaten version can
    always be replayed, which the vanilla game does not allow. Entry 2 needs
    the value entry 1 leaves behind, entry 3 the value entry 2 leaves, and so
    on, so a multi-part level unlocks in order rather than all at once.

    Both stubs compare LEVEL_PROGRESS[level] against the entry's own required
    value at node[12]. Vanilla nodes carry 0 at node[15] and skip the test
    entirely.

    The leaf stub also LATCHES: whenever it sees the level's completion byte
    higher than the recorded progress, it records the new value. The map is
    always redrawn between finishing a level and picking anything, so no
    separate hook on level completion is needed.
    """
    # --- CheckWorldMapNodeVisible, leaf case --------------------------------
    # The original block clobbers r3 (the node), so the whole thing is
    # replaced and the node kept in r8. r0/r3-r8 are all scratch this early.
    leaf = [
        _mr(8, 3),                      # keep the node pointer
        _lbz(4, 1, 3),                  # level id
        _lbz(5, 15, 3),                 # variation number; 0 on vanilla nodes
        _lis(0, (LEVEL_RECORD_BASE >> 16) & 0xFFFF),
        _ori(0, 0, LEVEL_RECORD_BASE & 0xFFFF),
        _rlwinm(3, 4, 6, 0, 25),        # level * 0x40
        _add(3, 0, 3),                  # r3 = the level's record
    ] + _progress_address(4, 6) + [

        # latch: progress = max(progress, completion byte)
        _lbz(0, 0, 3),                  # the game's own completion value
        _lbz(7, 0, 6),                  # what we have recorded
        _cmplw(0, 7),
        ("ble", "no_latch"),
        _stb(0, 0, 6),
        ("label", "no_latch"),

        _lbz(0, 2, 3),
        _rlwinm(0, 0, 25, 31, 31),      # bit 7 = "shown on the map"
        _cmpwi(0, 0),
        ("beq", "hidden"),              # the level itself is not shown yet
        _cmpwi(5, 0),
        ("beq", "visible"),             # a vanilla node - nothing more to ask

        _lbz(0, 12, 8),                 # the value this entry requires
        _lbz(7, 0, 6),                  # progress reached so far
        _cmplw(7, 0),
        ("blt", "hidden"),              # not reached yet
        ("label", "visible"),
        ("b", VISIBLE_BIT_LEAF_YES),
        ("label", "hidden"),
        ("b", VISIBLE_BIT_LEAF_NO),
    ]
    address = _emit(patcher, leaf)
    patcher.patch_word(VISIBLE_BIT_LEAF_BLOCK, _b(VISIBLE_BIT_LEAF_BLOCK, address))
    logger.info(f"[mechanic_world_map_variations] leaf visibility stub at {hex(address)}")

    # --- UpdateWorldMapCursorSnap, cursor snapping -------------------------
    # Replaces the bit-7 extract. NOT a call boundary - the function carries
    # on afterwards expecting its registers intact - so everything borrowed
    # beyond r0 is saved and restored. On entry r0 is the raw +2 byte and r5
    # the node. No latching here; the leaf stub covers that.
    cursor = [
        _stwu(1, -32, 1),
        _stw(4, 8, 1),
        _stw(6, 12, 1),
        _stw(7, 16, 1),

        _rlwinm(0, 0, 25, 31, 31),      # the instruction being replaced
        _cmpwi(0, 0),
        ("beq", "done"),                # already hidden
        _lbz(4, 15, 5),                 # variation number
        _cmpwi(4, 0),
        ("beq", "shown"),               # a vanilla node

        _lbz(4, 1, 5),                  # level id
    ] + _progress_address(4, 6) + [
        _lbz(7, 0, 6),                  # progress reached
        _lbz(4, 12, 5),                 # the value this entry requires
        _cmplw(7, 4),
        ("blt", "hide"),

        ("label", "shown"),
        _li(0, 1),
        ("b", "done"),
        ("label", "hide"),
        _li(0, 0),

        ("label", "done"),
        _lwz(4, 8, 1),
        _lwz(6, 12, 1),
        _lwz(7, 16, 1),
        _addi(1, 1, 32),

        # The instruction this stub replaced was `rlwinm.` - it SET CR0, and
        # the caller's very next instruction is `beq` on that result to skip an
        # unselectable node. Returning without setting CR0 left the caller
        # branching on whatever our last compare happened to leave, which
        # inverted the outcome: an entry whose progress exactly equalled its
        # requirement compared EQ and was skipped, while one that failed the
        # test compared LT and was selectable.
        _cmpwi(0, 0),
        _blr(),
    ]
    address = _emit(patcher, cursor)
    for call_site in CURSOR_VISIBLE_TESTS:
        patcher.patch_word(call_site, _bl(call_site, address))
    logger.info(
        f"[mechanic_world_map_variations] cursor visibility stub at "
        f"{hex(address)}, attached to {len(CURSOR_VISIBLE_TESTS)} site(s)"
    )