"""
Progressive attribute proficiencies. Disables the game's own cross-element
trade-off behavior in UpdateElementalMastery (0x80070A88) entirely, then
drives each of the 6 elemental mastery levels (elemental_mastery_levels,
0x8025d060-0x8025d065) directly off progressive_fire/water/earth/wood/
neutral/mech_attribute (LK2Client.STORAGE_ADDRESSES, 0x8025e657-0x8025e65c,
sequential in the same 0=fire..5=mech order as the game's own data) via a
per-tick mechanic registered with ISOPatcher.register_tick_mechanic.

UpdateElementalMastery(playerIndex, element, masteryGain) is XP-based, not
level-based: each call adds masteryGain to a running per-element XP total,
then recomputes a level (1-8) from fixed thresholds. It also normally
subtracts XP from the other 5 elements as a trade-off penalty - every one
of those penalty branches converges to the same final level-recalculation
loop (confirmed via disassembly: all branch to 0x80070cc8), so replacing
the single branch at 0x80070afc with an unconditional jump straight there
skips the entire penalty chain while leaving the target element's own XP
update and the final loop (level recalculation + QueueTextFadeEntry UI
notification) completely untouched.

masteryGain per call is kept small (100) - deliberately less than the
smallest level threshold gap (500, level 1->2) - so a single call can
never skip past more than one level at once, preserving one UI
notification per level gained rather than silently skipping several.
Loop is capped at 200 iterations per element per tick as a safety net
(200*100=20000, comfortably past the level-8 threshold of 14000).

Also NOPs ProcessCardActivation's own natural call to
UpdateElementalMastery (0x80070ed4) - playing a card normally grants
mastery XP to its own element directly, entirely separate from the
cross-element penalty chain disabled above. Confirmed via a full grep
across the decompiled source that this is the ONLY natural call site
to UpdateElementalMastery in the entire game. Without this NOP, natural
per-card progression still happens on top of AP-granted progression
(confirmed by the user in-game: playing a card still increased an
attribute even with the penalty chain already disabled) - the penalty
skip alone does not disable natural progression, only its cross-element
side effect.
"""

from worlds.LostKingdoms2.LK2Client import STORAGE_ADDRESSES

PROGRESSIVE_FIRE_ATTRIBUTE = STORAGE_ADDRESSES['progressive_fire_attribute']['address']
ELEMENTAL_MASTERY_LEVELS = 0x8025D060
UPDATE_ELEMENTAL_MASTERY = 0x80070A88

PENALTY_CHAIN_SKIP_BRANCH = 0x80070afc
PENALTY_CHAIN_SKIP_TARGET = 0x80070cc8

# ProcessCardActivation's own natural call to UpdateElementalMastery
# (playing a card grants mastery XP to its own element directly, no
# trade-off involved) - this is a SEPARATE call site from the
# trade-off penalty chain above, and NOPing the penalty chain alone
# does nothing to stop it. Confirmed this is the ONLY natural call
# site to UpdateElementalMastery anywhere in the game (single grep
# hit besides the function's own definition) - our own per-tick
# stub calls UpdateElementalMastery directly too, from the cave, so
# NOPing this one call site fully disables natural progression while
# leaving AP-driven progression completely unaffected.
NATURAL_PROGRESSION_CALL_SITE = 0x80070ed4

NUM_ELEMENTS = 6
MASTERY_GAIN_PER_CALL = 100
MAX_ITERATIONS_PER_ELEMENT = 200
MAX_ATTRIBUTE_LEVEL = 8  # UpdateElementalMastery's level can never exceed this
# Baseline value each element initializes to on first run (never-set = still
# 0). Fire/Water/Earth/Wood start at 3, Neutral/Mech start at 1.
BASELINE_VALUES = [3, 3, 3, 3, 1, 1]


def _lis(rD, imm16):
    return 0x3C000000 | (rD << 21) | (imm16 & 0xFFFF)


def _ori(rA, rS, imm16):
    return 0x60000000 | (rS << 21) | (rA << 16) | (imm16 & 0xFFFF)


def _lbz(rD, offset, rA):
    return 0x88000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _lbzx(rD, rA, rB):
    return 0x7C0000AE | (rD << 21) | (rA << 16) | (rB << 11)


def _stb(rS, offset, rA):
    return 0x98000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stw(rS, offset, rA):
    return 0x90000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stwu(rS, offset, rA):
    return 0x94000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _lwz(rD, offset, rA):
    return 0x80000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _addi(rD, rA, simm):
    return 0x38000000 | (rD << 21) | (rA << 16) | (simm & 0xFFFF)


def _li(rD, simm):
    return _addi(rD, 0, simm)


def _mr(rD, rS):
    return 0x7C000378 | (rS << 21) | (rD << 16) | (rS << 11)


def _add(rD, rA, rB):
    return 0x7C000214 | (rD << 21) | (rA << 16) | (rB << 11)


def _mflr(rD):
    return 0x7C0802A6 | (rD << 21)


def _mtlr(rS):
    return 0x7C0803A6 | (rS << 21)


def _cmplw(rA, rB):
    return 0x7C000040 | (rA << 16) | (rB << 11)


def _cmpwi(rA, simm):
    return 0x2C000000 | (rA << 16) | (simm & 0xFFFF)


def _ble(from_addr, to_addr):
    return 0x40810000 | ((to_addr - from_addr) & 0xFFFC)


def _bge(from_addr, to_addr):
    return 0x40800000 | ((to_addr - from_addr) & 0xFFFC)


def _beq(from_addr, to_addr):
    return 0x41820000 | ((to_addr - from_addr) & 0xFFFC)


def _bne(from_addr, to_addr):
    return 0x40820000 | ((to_addr - from_addr) & 0xFFFC)


def _b(from_addr, to_addr):
    return 0x48000000 | ((to_addr - from_addr) & 0x3FFFFFC)


def _build_stub(patcher):
    fire_hi = (PROGRESSIVE_FIRE_ATTRIBUTE >> 16) & 0xFFFF
    fire_lo = PROGRESSIVE_FIRE_ATTRIBUTE & 0xFFFF
    lvl_hi = (ELEMENTAL_MASTERY_LEVELS >> 16) & 0xFFFF
    lvl_lo = ELEMENTAL_MASTERY_LEVELS & 0xFFFF

    # Small baseline lookup table, one byte per element, packed into words.
    baseline_table_addr = patcher.alloc_cave(2 * 4)
    b = BASELINE_VALUES
    word0 = (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]
    word1 = (b[4] << 24) | (b[5] << 16)
    patcher.patch_word(baseline_table_addr, word0)
    patcher.patch_word(baseline_table_addr + 4, word1)
    base_hi = (baseline_table_addr >> 16) & 0xFFFF
    base_lo = baseline_table_addr & 0xFFFF

    instructions = [
        _stwu(1, -48, 1),
        _mflr(0),
        _stw(0, 52, 1),
        _stw(28, 32, 1),
        _stw(29, 36, 1),
        _stw(30, 40, 1),
        _stw(31, 44, 1),
        _li(28, 0),                     # r28 = elementIndex
    ]

    outer_loop_idx = len(instructions)
    instructions += [
        _cmpwi(28, NUM_ELEMENTS),
        None,   # bge outer_done (filled below)
        _lis(29, fire_hi),              # r29 = &progressive_fire_attribute
        _ori(29, 29, fire_lo),
        _add(29, 29, 28),               # r29 += elementIndex
    ]
    # One-time baseline init: if this element's progressive value has never
    # been set (still 0), initialize it from the baseline lookup table.
    # Naturally only takes effect once, since these values should only ever
    # increase afterward (AP-granted attribute levels never decrease back
    # to 0).
    instructions += [
        _lbz(3, 0, 29),
        _cmpwi(3, 0),
        None,   # bne skip_init (filled below)
        _lis(5, base_hi),               # r5 = &baseline table
        _ori(5, 5, base_lo),
        _lbzx(3, 5, 28),                # r3 = baseline_table[elementIndex]
        _stb(3, 0, 29),
    ]
    bne_init_idx = len(instructions) - 5
    skip_init_idx = len(instructions)

    instructions += [
        _lis(30, lvl_hi),               # r30 = &elemental_mastery_levels
        _ori(30, 30, lvl_lo),
        _add(30, 30, 28),               # r30 += elementIndex
        _li(31, MAX_ITERATIONS_PER_ELEMENT),  # r31 = inner safety counter
    ]

    inner_loop_idx = len(instructions)
    instructions += [
        _lbz(3, 0, 29),                 # r3 = desired level
    ]
    # Safety clamp: UpdateElementalMastery's level can never exceed
    # MAX_ATTRIBUTE_LEVEL (8) regardless of how much XP accumulates, so if
    # the stored desired value is ever set above that, "desired > current"
    # would never become false - this would silently burn through the full
    # 200-iteration safety cap every single tick, forever, looking like a
    # freeze even though each individual tick does terminate.
    instructions += [
        _cmpwi(3, MAX_ATTRIBUTE_LEVEL),
        None,   # ble skip_clamp (filled below)
        _li(3, MAX_ATTRIBUTE_LEVEL),
    ]
    skip_clamp_idx = len(instructions)

    instructions += [
        _lbz(4, 0, 30),                 # r4 = current level
        _cmplw(3, 4),
        None,   # ble inner_done (filled below)
        _cmpwi(31, 0),
        None,   # beq inner_done (filled below)
        _addi(31, 31, -1),
        _li(3, 0),                      # playerIndex = 0
        _mr(4, 28),                     # element = elementIndex
        _li(5, MASTERY_GAIN_PER_CALL),  # masteryGain
        None,   # bl UpdateElementalMastery (filled below)
        None,   # b inner_loop (filled below)
    ]
    inner_done_idx = len(instructions)

    instructions += [
        _addi(28, 28, 1),               # elementIndex++
        None,   # b outer_loop (filled below)
    ]
    outer_done_idx = len(instructions)

    epilogue = [
        _lwz(0, 52, 1),
        _mtlr(0),
        _lwz(28, 32, 1),
        _lwz(29, 36, 1),
        _lwz(30, 40, 1),
        _lwz(31, 44, 1),
        _addi(1, 1, 48),
        0x4E800020,  # blr
    ]

    total_words = len(instructions) + len(epilogue)
    stub_addr = patcher.alloc_cave(total_words * 4)

    instructions[outer_loop_idx + 1] = _bge(stub_addr + (outer_loop_idx + 1) * 4,
                                             stub_addr + outer_done_idx * 4)
    instructions[bne_init_idx] = _bne(stub_addr + bne_init_idx * 4,
                                       stub_addr + skip_init_idx * 4)
    instructions[inner_loop_idx + 2] = _ble(stub_addr + (inner_loop_idx + 2) * 4,
                                             stub_addr + skip_clamp_idx * 4)
    instructions[inner_loop_idx + 6] = _ble(stub_addr + (inner_loop_idx + 6) * 4,
                                             stub_addr + inner_done_idx * 4)
    instructions[inner_loop_idx + 8] = _beq(stub_addr + (inner_loop_idx + 8) * 4,
                                             stub_addr + inner_done_idx * 4)
    instructions[inner_loop_idx + 13] = patcher.make_bl(stub_addr + (inner_loop_idx + 13) * 4,
                                                         UPDATE_ELEMENTAL_MASTERY)
    instructions[inner_loop_idx + 14] = _b(stub_addr + (inner_loop_idx + 14) * 4,
                                            stub_addr + inner_loop_idx * 4)
    instructions[outer_done_idx - 1] = _b(stub_addr + (outer_done_idx - 1) * 4,
                                           stub_addr + outer_loop_idx * 4)

    patcher.write_code(stub_addr, instructions + epilogue)
    return stub_addr



def apply(patcher):
    # Skip the entire cross-element penalty if/else-if chain - every branch
    # in it converges to the same final level-recalculation loop, so this
    # single unconditional jump disables all trade-off penalties while
    # leaving the target element's own update and the UI notification
    # logic fully intact.
    patcher.patch_word(PENALTY_CHAIN_SKIP_BRANCH,
                        patcher.make_b(PENALTY_CHAIN_SKIP_BRANCH, PENALTY_CHAIN_SKIP_TARGET))

    # NOP ProcessCardActivation's own natural UpdateElementalMastery call -
    # without this, playing a card still grants natural mastery XP to its
    # own element (confirmed by the user in-game), even with the
    # cross-element penalty disabled above - the penalty skip and the
    # natural-progression disable are two entirely separate fixes.
    patcher.patch_word(NATURAL_PROGRESSION_CALL_SITE, 0x60000000)

    stub_addr = _build_stub(patcher)
    patcher.register_tick_mechanic(stub_addr)