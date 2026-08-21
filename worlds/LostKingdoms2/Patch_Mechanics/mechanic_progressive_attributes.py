"""
Progressive attribute proficiencies. Disables the game's own cross-element
trade-off behavior in UpdateElementalMastery (0x80070A88) entirely, then
drives each of the 6 elemental mastery levels (elemental_mastery_levels,
0x8025d060-0x8025d065) directly off progressive_fire/water/earth/wood/
neutral/mech_attribute (LK2Client.STORAGE_ADDRESSES, 0x8025e657-0x8025e65c,
sequential in the same 0=fire..5=mech order as the game's own data) via a
per-tick mechanic registered with ISOPatcher.register_tick_mechanic.

The progressive_X_attribute addresses are the AP client's own storage -
this mechanic only ever READS them, never writes. An earlier version
initialized each one to its own baseline value on first read if still 0,
which silently overwrote whatever the client had (or was about to) store
there - a genuine bug, not a deliberate design. progressive_X_attribute
holds a COUNT of progressive items received (0, 1, 2, ...), not an
absolute target level - the actual target level is BASELINE_VALUES[element]
+ progressive_X_attribute, computed fresh every time without ever writing
back to the trigger address itself. E.g. fire's own baseline is 3, so a
progressive_fire_attribute of 2 means "increase fire mastery to 5".

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

masteryGain per call is NOT applied directly - UpdateElementalMastery
itself multiplies it by (16 - currentLevel) before adding it to the
running XP total (confirmed via disassembly at 0x80070988, reading
elemental_mastery_levels[element] - the SAME byte this mechanic itself
also reads - as that multiplier's own input). This means the effective XP
added per call varies with the element's CURRENT level: at level 1 (the
worst case, multiplier 15) it's masteryGain*15; at level 7 (multiplier 9)
it's masteryGain*9. A naive "just keep masteryGain under the smallest
threshold gap (500)" reasoning - which an earlier version of this
mechanic used, picking 100 - is wrong, since it ignores this multiplier
entirely: 100*15=1500 at level 1 alone, which lands past the level-2
threshold (500) AND the level-3 threshold (1500) in a single call,
confirmed live as a real, reported bug (setting a progressive attribute
by 1 produced an in-game jump of 2 levels, every time, specifically for
neutral/mech - the two elements whose baseline level is 1, i.e. the only
elements that could ever actually BE at the worst-case level when a call
happens, since fire/water/earth/wood start at baseline level 3).

MASTERY_GAIN_PER_CALL is chosen so that masteryGain*(16-level) stays
strictly under the gap to the NEXT level, at every level 1-7 (the
level values a call could ever actually execute at, since the loop
always stops once current>=desired and desired is clamped to 8) - the
binding constraint is level 1 specifically, since it has both the
largest multiplier (15) AND the smallest gap (500): 25*15=375 < 500,
with room to spare, and comfortably satisfies every other, less
restrictive level (e.g. level 7: 25*9=225 < 3500).
Loop is capped at 200 iterations per element per tick as a safety net -
still comfortably sufficient at masteryGain=25: reaching the level-8
threshold (14000 XP) takes roughly 14000/(25*~11 average multiplier)
≈ 51 calls in the worst case, well under the 200-call cap.
"""

from worlds.LostKingdoms2.LK2Client import STORAGE_ADDRESSES

PROGRESSIVE_FIRE_ATTRIBUTE = STORAGE_ADDRESSES['progressive_fire_attribute']['address']
ELEMENTAL_MASTERY_LEVELS = 0x8025D060
UPDATE_ELEMENTAL_MASTERY = 0x80070A88

# ProcessCardActivation's own bl to UpdateElementalMastery (0x80070E0C +
# 0xc8), confirmed via disassembly: exactly one bl-to-0x80070A88 call site
# exists within ProcessCardActivation, matching main_dol.c's own decompiled
# call right after the AllocateLinkedGroupSlot/memset setup for a newly
# activated card. The very next line in the decompiled source is an
# unrelated store that doesn't use UpdateElementalMastery's own return
# value, confirming this call is safe to NOP outright.
NATURAL_PROGRESSION_CALL_SITE = 0x80070ed4

PENALTY_CHAIN_SKIP_BRANCH = 0x80070afc
PENALTY_CHAIN_SKIP_TARGET = 0x80070cc8

NUM_ELEMENTS = 6
MASTERY_GAIN_PER_CALL = 25
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

    # Label-based fill system (index/kind/target-label recorded at the point
    # each placeholder is created, then resolved once stub_addr is known) -
    # deliberately NOT hardcoded "inner_loop_idx + N" offsets: a previous
    # version of this stub used exactly that style and, confirmed by
    # actually building and inspecting it, silently filled several branches
    # at the WRONG index (an insertion earlier in the function shifted every
    # offset after it by a fixed amount the hardcoded numbers were never
    # updated to match) - four placeholders were left as literal None words
    # in the final, emitted code. This pattern can't go out of sync the same
    # way, since nothing after this point needs to know any instruction's
    # own absolute position ahead of time.
    instructions = []
    fills = []
    labels = {}

    instructions += [
        _stwu(1, -48, 1),
        _mflr(0),
        _stw(0, 52, 1),
        _stw(27, 28, 1),
        _stw(28, 32, 1),
        _stw(29, 36, 1),
        _stw(30, 40, 1),
        _stw(31, 44, 1),
        _li(28, 0),                     # r28 = elementIndex
    ]

    labels["outer_loop"] = len(instructions)
    instructions.append(_cmpwi(28, NUM_ELEMENTS))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "bge", "outer_done"))
    instructions += [
        _lis(29, fire_hi),              # r29 = &progressive_fire_attribute
        _ori(29, 29, fire_lo),
        _add(29, 29, 28),               # r29 += elementIndex (READ-ONLY from here on - AP client's own storage)
        _lis(5, base_hi),               # r5 = &baseline table
        _ori(5, 5, base_lo),
        _lbzx(27, 5, 28),                # r27 = baseline_table[elementIndex], held for the whole inner loop below
        _lis(30, lvl_hi),               # r30 = &elemental_mastery_levels
        _ori(30, 30, lvl_lo),
        _add(30, 30, 28),               # r30 += elementIndex
        _li(31, MAX_ITERATIONS_PER_ELEMENT),  # r31 = inner safety counter
    ]

    labels["inner_loop"] = len(instructions)
    instructions += [
        _lbz(3, 0, 29),                 # r3 = progressive_X_attribute (item count, NOT the target level)
        _add(3, 3, 27),                 # r3 = baseline + item count = actual desired level
        _cmpwi(3, MAX_ATTRIBUTE_LEVEL),
    ]
    # Safety clamp: UpdateElementalMastery's level can never exceed
    # MAX_ATTRIBUTE_LEVEL (8) regardless of how much XP accumulates, so if
    # baseline+count ever computes above that, "desired > current" would
    # never become false - this would silently burn through the full
    # 200-iteration safety cap every single tick, forever, looking like a
    # freeze even though each individual tick does terminate.
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "ble", "skip_clamp"))
    instructions.append(_li(3, MAX_ATTRIBUTE_LEVEL))
    labels["skip_clamp"] = len(instructions)

    instructions += [
        _lbz(4, 0, 30),                 # r4 = current level
        _cmplw(3, 4),
    ]
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "ble", "inner_done"))
    instructions.append(_cmpwi(31, 0))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "beq", "inner_done"))
    instructions += [
        _addi(31, 31, -1),
        _li(3, 0),                      # playerIndex = 0
        _mr(4, 28),                     # element = elementIndex
        _li(5, MASTERY_GAIN_PER_CALL),  # masteryGain
    ]
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "bl", UPDATE_ELEMENTAL_MASTERY))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "b", "inner_loop"))
    labels["inner_done"] = len(instructions)

    instructions.append(_addi(28, 28, 1))  # elementIndex++
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "b", "outer_loop"))
    labels["outer_done"] = len(instructions)

    epilogue = [
        _lwz(0, 52, 1),
        _mtlr(0),
        _lwz(27, 28, 1),
        _lwz(28, 32, 1),
        _lwz(29, 36, 1),
        _lwz(30, 40, 1),
        _lwz(31, 44, 1),
        _addi(1, 1, 48),
        0x4E800020,  # blr
    ]

    total_words = len(instructions) + len(epilogue)
    stub_addr = patcher.alloc_cave(total_words * 4)

    for idx, kind, target in fills:
        from_addr = stub_addr + idx * 4
        if kind == "bl":
            instructions[idx] = patcher.make_bl(from_addr, target)
        elif kind == "b":
            instructions[idx] = _b(from_addr, stub_addr + labels[target] * 4)
        elif kind == "beq":
            instructions[idx] = _beq(from_addr, stub_addr + labels[target] * 4)
        elif kind == "ble":
            instructions[idx] = _ble(from_addr, stub_addr + labels[target] * 4)
        elif kind == "bge":
            instructions[idx] = _bge(from_addr, stub_addr + labels[target] * 4)
        else:
            raise ValueError(f"unknown fill kind: {kind}")

    assert all(instr is not None for instr in instructions), \
        "unfilled branch placeholder remained in mechanic_progressive_attributes stub"

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