import struct

from worlds.LostKingdoms2.LK2Client import STORAGE_ADDRESSES

KEY_ITEM_LOCATION = STORAGE_ADDRESSES['key_item_location']['address']
WRITE_SCRIPT_RESULT = 0x800893A4

OPCODE_TABLE_BASE = 0x80165a38
# The script opcode dispatcher is:
#     lwzx r12, OPCODE_TABLE_BASE, opcode*4 ; mtctr r12 ; bctrl
# with NO bounds check - only "opcode != 0" and "(opcode & 0x8000) == 0".
# So any index below 0x8000 dispatches, and registering a handler is just a
# matter of writing a code pointer at OPCODE_TABLE_BASE + index*4.
#
# The real table is 498 entries (0..497, ending at 0x80166200) and every one
# of them is populated - there is no spare slot inside it. Index 499 was
# used previously because the word there reads zero in a clean DOL, but that
# word is NOT spare: it sits at +0x1C from 0x801661E8, an address used as a
# base by a dozen instructions, in the middle of a float constant pool
# (1.0 at +0x00, 0.5 at +0x08). Writing a code pointer into it corrupts that
# pool, and anything the game writes back through that base corrupts our
# handler pointer in turn.
#
# 5385 (0x8016AE5C) instead: the middle of the only >=32-word run of zeros
# below index 0x8000, 128 bytes clear of the nearest address any lis+offset
# pair in the DOL resolves to, sitting in the padding between two byte
# lookup tables in data3. Verified zero at build time below before writing.
#
# This is safer than 499, not provably perfect - it is still a word the game
# owns, and nothing here proves no runtime code writes to it. If the handler
# ever stops firing, or a crash points at a bad branch target out of the
# dispatcher, suspect this slot first.
NEW_OPCODE_INDEX = 5385

# NOTE: this opcode is registered but not yet applied to every relevant
# location. Doors in Nobleman's Residence check the real key-item bitmask
# via vanilla GetKeyItemObtained (see mechanic_code_modifications.py Group
# 1) - this opcode is for specific reads elsewhere that should be based on
# our own AP "locations" bitmask instead. Those call sites are added
# incrementally as they're identified.

ORIGINAL_OPCODE = 135

FOSSIL_BONEYARD_ISO_OFFSET = 0xb03dfc0

# File-relative offsets within Fossil Boneyard (s17.pds) of the 9 per-fossil
# spawn-condition checks (each immediately followed by its own conditional
# jump - "if already obtained, don't spawn"). Deliberately NOT touching the
# separate 9-in-a-row "all fossils placed at the stone" completion gate
# elsewhere in the same file (offsets 0x426008-0x4260a8) - that's a genuine
# in-game puzzle mechanic (skeletal dragon spawn) unrelated to AP locations.
FOSSIL_BONEYARD_SPAWN_CHECK_OFFSETS = [
    0x422944, 0x4229b4, 0x422a24, 0x422a94, 0x422b04,
    0x422b74, 0x422be4, 0x422c54, 0x422cc4,
]

S20_ISO_OFFSET = 0xbbe0140

# File-relative offset within s20.pds of the "has Stone of Sealing
# already been obtained" check (opcode 135, argument 28). CORRECTED:
# the 3 occurrences at argument 27 (0x414998, 0x414e64, 0x415168) were
# originally, incorrectly identified as Stone of Sealing under a 0-
# indexed reading of lost_kingdoms_2_key_items - cross-checking
# against s18.pds and s21.pds later confirmed the game's own internal
# key item IDs are actually 1-indexed (id = list_position + 1, not
# list_position directly). Under the corrected scheme, argument 27 is
# actually Castle Gate Key, and argument 28 (the single occurrence at
# 0x414fa4) is the real Stone of Sealing check - confirmed by the user
# directly ("a single check... sounds correct").
S20_STONE_OF_SEALING_CHECK_OFFSETS = [0x414fa4]

S21_ISO_OFFSET = 0xbffc1e0

# File-relative offsets within s21.pds of 4 sequential "has this blade
# already been obtained" checks (opcode 135, argcount 2) - one per
# blade (key item indices 19/18/17/16). Redirecting to opcode 499
# (always reports "not obtained") makes the branch that follows each
# check always take its own "stay active" skip path, using its own,
# original, correct skip amount - confirmed in-game this correctly
# keeps puzzles active until completed. This DOES also affect
# pedestal-placement logic, which reads the exact same computed
# result - confirmed via testing there's no way to decouple the two
# by touching only the check (an attempt to instead neutralize the
# branch's own skip-count directly, leaving the check as vanilla
# opcode 135, was tried and made things WORSE - it turned out
# "skip=0" means "always act as obtained", not "never skip", so it
# disabled every puzzle unconditionally; reverted). The
# pedestal-breaking side effect of this redirect remains an open,
# unresolved problem.
S21_BLADE_CHECK_OFFSETS = [0x4f8590, 0x4f860c, 0x4f8664, 0x4f86ac]

S10_ISO_OFFSET = 0x921dcc0

# File-relative offset within s10.pds of the "has Castle Gate Key
# already been obtained" check (opcode 135, argument 29 - key item
# index 28, Castle Gate Key, under the game's own 1-indexed key item
# scheme). 0x45bea4 was tried first (based on its own proximity to 3
# calls to ScriptOp_PlayNpcAnimation) and confirmed WRONG in-game.
# 0x45ba88 (the other opcode-135 occurrence for the same item)
# confirmed correct instead.
S10_CASTLE_GATE_KEY_MONSTER_SPAWN_OFFSETS = [0x45ba88]

S09_ISO_OFFSET = 0x8ce2220

# File-relative offsets within s09.pds of 2 of 3 opcode-135 "has Key
# to Fountain already been obtained" checks (argument 30 - key item
# index 29, Key to Fountain, under the game's own 1-indexed key item
# scheme). 0x52accc confirmed correct in-game (the user's own first
# guess). 0x52b508 now also confirmed needed. The 3rd occurrence
# (0x52b71c) remains untouched - not confirmed as AP-relevant.
S09_KEY_TO_FOUNTAIN_CHECK_OFFSETS = [0x52accc, 0x52b508]

S01_ISO_OFFSET = 0x68a4180

# File-relative offsets within s01.pds of both "has Keil Runestone
# already been obtained" checks (opcode 135, argument 26 - key item
# index 25, Keil Runestone, under the game's own 1-indexed key item
# scheme) that gate whether the level's own card-user NPC spawns -
# confirmed in-game the NPC currently spawns even with the runestone
# already obtained, the same missing-gate issue as levels 9/10/18/20.
# 5 other opcode-135 checks in this same file (argument 15, Mysterious
# Key) are unrelated and deliberately NOT touched.
S01_KEIL_RUNESTONE_CHECK_OFFSETS = [0x49f350, 0x49f58c]

S22_ISO_OFFSET = 0xc4ff5a0

# File-relative offset within s22.pds of the "has Ebin Runestone
# already been obtained" check (opcode 135, argument 25 - key item
# index 24, Ebin Runestone) that gates whether the level's own
# card-user NPC spawns. Only one occurrence in this file.
S22_EBIN_RUNESTONE_CHECK_OFFSETS = [0x485550]

S23_ISO_OFFSET = 0xc98b540

# File-relative offsets within s23.pds of all 3 "has Olf Runestone
# already been obtained" checks (opcode 135, argument 24 - key item
# index 23, Olf Runestone). A 4th, unrelated opcode-135 check in this
# same file (argument 15, Mysterious Key, same as seen in s01.pds) is
# deliberately NOT touched.
S23_OLF_RUNESTONE_CHECK_OFFSETS = [0x42b89c, 0x42d14c, 0x42d5e4]

S14_ISO_OFFSET = 0xa26d160

# File-relative offset within s14.pds of the single "has Jewel of Alanjah
# already been obtained" check (opcode 135, argument 20 - key item index 19,
# Jewel of Alanjah). This file contains exactly ONE opcode-135 check, so
# unlike s01/s20/s21/s23 there is no unrelated occurrence to avoid.
#
# Verified against the already-redirected s23 Mysterious Key check: the
# surrounding words are byte-for-byte identical (0x00040000 / 0x00000000
# before, 0x00040000 / argument / 0x00040012 after), with only the argument
# differing - so this is structurally the same construct the redirect
# handles, not a coincidental byte match.
S14_JEWEL_OF_ALANJAH_CHECK_OFFSETS = [0x4c465c]

# File-relative offsets within s20.pds of the 1st and 3rd of 3 "has
# Nebeth Runestone already been obtained" checks (opcode 135, argument
# 27 - key item index 26, Nebeth Runestone). Part of a sequential
# puzzle-gating chain of 8 checks in this same file (one per runestone
# plus this triple-occurrence one), matching the structural pattern
# seen in s21.pds's blade puzzles. Per the user, the 2nd occurrence
# (0x414e64) is left untouched - only the 1st and 3rd redirected.
S20_NEBETH_RUNESTONE_CHECK_OFFSETS = [0x414998, 0x415168]


def _lis(rD, imm16):
    return 0x3C000000 | (rD << 21) | (imm16 & 0xFFFF)


def _ori(rA, rS, imm16):
    return 0x60000000 | (rS << 21) | (rA << 16) | (imm16 & 0xFFFF)


def _lwz(rD, offset, rA):
    return 0x80000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _stw(rS, offset, rA):
    return 0x90000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stwu(rS, offset, rA):
    return 0x94000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _addi(rD, rA, simm):
    return 0x38000000 | (rD << 21) | (rA << 16) | (simm & 0xFFFF)


def _li(rD, simm):
    return _addi(rD, 0, simm)


def _mr(rD, rS):
    return 0x7C000378 | (rS << 21) | (rD << 16) | (rS << 11)


def _mflr(rD):
    return 0x7C0802A6 | (rD << 21)


def _mtlr(rS):
    return 0x7C0803A6 | (rS << 21)


def _slw(rA, rS, rB):
    return 0x7C000030 | (rS << 21) | (rA << 16) | (rB << 11)


def _and(rA, rS, rB):
    return 0x7C000038 | (rS << 21) | (rA << 16) | (rB << 11)


def _cmpwi(rA, simm):
    return 0x2C000000 | (rA << 16) | (simm & 0xFFFF)


def _beq(from_addr, to_addr):
    offset = to_addr - from_addr
    return 0x41820000 | (offset & 0xFFFC)


def _build_opcode_handler(patcher):
    hi = (KEY_ITEM_LOCATION >> 16) & 0xFFFF
    lo = KEY_ITEM_LOCATION & 0xFFFF

    stub_addr = patcher.alloc_cave(26 * 4)

    instructions = [
        _stwu(1, -16, 1),
        _mflr(0),
        _stw(0, 20, 1),
        _stw(31, 12, 1),
        _mr(31, 3),                          # save scriptInstruction
        _lwz(4, 8, 31),                      # r4 = scriptInstruction[2] = queried keyItemId
        _lis(3, hi),
        _ori(3, 3, lo),
        _lwz(3, 0, 3),                       # r3 = key_item_location (bitmask)
        _li(5, 1),
        _slw(5, 5, 4),                       # r5 = 1 << keyItemId
        _and(3, 5, 3),                       # r3 = bitmask & (1 << keyItemId)
        _cmpwi(3, 0),                        # is the bit set?
        _li(3, 0),                           # default: bit not set
        None,                                 # placeholder for beq, filled below
        _li(3, 1),                           # only runs if bit was set
        _mr(4, 3),                           # result -> r4
        _addi(3, 31, 12),                    # r3 = &scriptInstruction[3]
        None,                                 # placeholder for bl WriteScriptResult
        _li(0, 0),
        _stw(0, 0, 31),                      # *scriptInstruction = 0
        _lwz(0, 20, 1),
        _lwz(31, 12, 1),
        _mtlr(0),
        _addi(1, 1, 16),
        0x4E800020,                          # blr
    ]

    beq_addr = stub_addr + 14 * 4
    skip_addr = stub_addr + 16 * 4
    instructions[14] = _beq(beq_addr, skip_addr)

    bl_addr = stub_addr + 18 * 4
    instructions[18] = patcher.make_bl(bl_addr, WRITE_SCRIPT_RESULT)

    patcher.write_code(stub_addr, instructions)

    # Register this stub as opcode NEW_OPCODE_INDEX in the script dispatch table
    slot_addr = OPCODE_TABLE_BASE + NEW_OPCODE_INDEX * 4
    slot_iso = patcher.ram_to_iso(slot_addr)
    patcher.file.seek(slot_iso)
    existing = int.from_bytes(patcher.file.read(4), "big")
    if existing != 0:
        raise ValueError(
            f"Expected opcode slot {NEW_OPCODE_INDEX} ({hex(slot_addr)}) to be unused "
            f"(zero), found {hex(existing)} instead. Aborting rather than overwrite "
            f"something unexpected."
        )
    patcher.patch_word(slot_addr, stub_addr)

    return stub_addr


def _redirect_opcode_135_checks(patcher, iso_offset_base, rel_offsets, label):
    for rel_offset in rel_offsets:
        iso_offset = iso_offset_base + rel_offset

        patcher.file.seek(iso_offset)
        original = struct.unpack('>I', patcher.file.read(4))[0]
        original_opcode = original >> 16
        argcount = original & 0xFFFF

        if original_opcode != ORIGINAL_OPCODE:
            raise ValueError(
                f"Expected opcode {ORIGINAL_OPCODE} at {label}+{hex(rel_offset)} "
                f"(iso offset {hex(iso_offset)}), found {original_opcode} instead "
                f"(full word {hex(original)}). Aborting rather than overwrite something unexpected."
            )

        new_header = (NEW_OPCODE_INDEX << 16) | argcount
        patcher.file.seek(iso_offset)
        patcher.file.write(struct.pack('>I', new_header))


def apply(patcher):
    _build_opcode_handler(patcher)

    _redirect_opcode_135_checks(
        patcher,
        FOSSIL_BONEYARD_ISO_OFFSET,
        FOSSIL_BONEYARD_SPAWN_CHECK_OFFSETS,
        "Fossil Boneyard (s17.pds)",
    )

    _redirect_opcode_135_checks(
        patcher,
        S20_ISO_OFFSET,
        S20_STONE_OF_SEALING_CHECK_OFFSETS,
        "s20.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S21_ISO_OFFSET,
        S21_BLADE_CHECK_OFFSETS,
        "s21.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S10_ISO_OFFSET,
        S10_CASTLE_GATE_KEY_MONSTER_SPAWN_OFFSETS,
        "s10.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S09_ISO_OFFSET,
        S09_KEY_TO_FOUNTAIN_CHECK_OFFSETS,
        "s09.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S01_ISO_OFFSET,
        S01_KEIL_RUNESTONE_CHECK_OFFSETS,
        "s01.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S22_ISO_OFFSET,
        S22_EBIN_RUNESTONE_CHECK_OFFSETS,
        "s22.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S23_ISO_OFFSET,
        S23_OLF_RUNESTONE_CHECK_OFFSETS,
        "s23.pds",
    )

    _redirect_opcode_135_checks(
        patcher,
        S20_ISO_OFFSET,
        S20_NEBETH_RUNESTONE_CHECK_OFFSETS,
        "s20.pds (Nebeth Runestone)",
    )

    _redirect_opcode_135_checks(
        patcher,
        S14_ISO_OFFSET,
        S14_JEWEL_OF_ALANJAH_CHECK_OFFSETS,
        "s14.pds (Jewel of Alanjah)",
    )