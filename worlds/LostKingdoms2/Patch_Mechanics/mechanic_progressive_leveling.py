"""
Progressive leveling. Disables the game's own XP-based leveling entirely
and instead drives player level directly off progressive_leveling
(LK2Client.STORAGE_ADDRESSES, 0x8025e656) via a per-tick mechanic
registered with mechanic_per_tick_hook - the AP client writes there, and
this mechanic calls the game's own ProcessLevelUp (0x80073674) repeatedly
until playerLevel (0x8025d02c) catches up.

progressive_leveling is the AP client's own storage - this mechanic only
ever READS it, never writes. An earlier version initialized it to
PROGRESSIVE_LEVELING_BASELINE on first read if still 0, which silently
overwrote whatever the client had (or was about to) store there - a
genuine bug, not a deliberate design (the same bug also existed, and was
also fixed, in mechanic_progressive_attributes.py). progressive_leveling
holds a COUNT of progressive level-up items received, not an absolute
target level - the actual target level is PROGRESSIVE_LEVELING_BASELINE +
progressive_leveling, computed fresh every time without ever writing back
to the trigger address itself.

ProcessLevelUp gates on three ANDed conditions: DAT_80209277=='\\0' (not in
a cutscene-driven player-state), requiredXP<=playerExp, and playerLevel!=20
(max level). We NOP only the XP comparison (0x800736d0) - the cutscene and
max-level gates stay fully intact, so this mechanic can never level the
player up mid-cutscene or past 20. Confirmed ProcessLevelUp itself doesn't
depend on being in a level: GetCharacterFormStats operates on a fixed
static address (not a dynamic in-level entity), and its other calls
(SpawnFloatingText, QueueTextFadeEntry) are both null/bounds-checked with
no crash risk if called from the world map.

Also NOPs the original call site in AddPlayerEXP (0x8007d0f8) - otherwise,
with the XP check disabled, any normal XP gain from combat would trigger a
free level-up on top of AP-granted ones.

Loop is capped at 20 iterations (the max possible level) as a safety net -
guarantees termination even if ProcessLevelUp silently declines to level up
(e.g. mid-cutscene) rather than looping forever.
"""

from worlds.LostKingdoms2.LK2Client import STORAGE_ADDRESSES

PROGRESSIVE_LEVELING = STORAGE_ADDRESSES['progressive_leveling']['address']
PLAYER_LEVEL = 0x8025D02C
PROCESS_LEVEL_UP = 0x80073674

XP_CHECK_BRANCH = 0x800736d0
ADD_PLAYER_EXP_CALL_SITE = 0x8007d0f8

MAX_LEVEL_SAFETY_CAP = 20
MAX_LEVEL = 20  # ProcessLevelUp's own hard cap (playerLevel != 20 gate)
PROGRESSIVE_LEVELING_BASELINE = 1


def _lis(rD, imm16):
    return 0x3C000000 | (rD << 21) | (imm16 & 0xFFFF)


def _ori(rA, rS, imm16):
    return 0x60000000 | (rS << 21) | (rA << 16) | (imm16 & 0xFFFF)


def _lbz(rD, offset, rA):
    return 0x88000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


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


def _beq(from_addr, to_addr):
    return 0x41820000 | ((to_addr - from_addr) & 0xFFFC)


def _bne(from_addr, to_addr):
    return 0x40820000 | ((to_addr - from_addr) & 0xFFFC)


def _b(from_addr, to_addr):
    return 0x48000000 | ((to_addr - from_addr) & 0x3FFFFFC)


def _build_stub(patcher):
    pl_hi = (PROGRESSIVE_LEVELING >> 16) & 0xFFFF
    pl_lo = PROGRESSIVE_LEVELING & 0xFFFF
    lvl_hi = (PLAYER_LEVEL >> 16) & 0xFFFF
    lvl_lo = PLAYER_LEVEL & 0xFFFF

    # Label-based fill system, not hardcoded "loop_idx + N" offsets - see
    # mechanic_progressive_attributes.py's own _build_stub docstring for why
    # (confirmed, by actually building and inspecting that mechanic's own,
    # differently-structured stub, that hardcoded offsets silently left
    # several branches unfilled after an unrelated edit shifted everything
    # after it). Applying the same, safer pattern here even though this
    # mechanic's own structure hasn't shown the same symptom, since the
    # underlying fragility is the same.
    instructions = []
    fills = []
    labels = {}

    instructions += [
        _stwu(1, -32, 1),
        _mflr(0),
        _stw(0, 36, 1),
        _stw(29, 20, 1),
        _stw(30, 24, 1),
        _stw(31, 28, 1),
        _lis(29, pl_hi),                # r29 = &progressive_leveling (READ-ONLY - AP client's own storage)
        _ori(29, 29, pl_lo),
        _lis(30, lvl_hi),               # r30 = &playerLevel
        _ori(30, 30, lvl_lo),
        _li(31, MAX_LEVEL_SAFETY_CAP),  # r31 = safety counter
    ]

    labels["loop"] = len(instructions)
    instructions += [
        _lbz(3, 0, 29),                 # r3 = progressive_leveling (item count, NOT the target level)
        _addi(3, 3, PROGRESSIVE_LEVELING_BASELINE),  # r3 = baseline + item count = actual desired level
        _cmpwi(3, MAX_LEVEL),
    ]
    # Safety clamp: playerLevel can never exceed MAX_LEVEL (ProcessLevelUp's
    # own hard gate), so if baseline+count ever computes above it, "desired
    # > current" would never become false - this would silently burn
    # through the full 20-iteration safety cap every single tick, forever,
    # looking like a freeze even though each individual tick does
    # terminate.
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "ble", "skip_clamp"))
    instructions.append(_li(3, MAX_LEVEL))
    labels["skip_clamp"] = len(instructions)

    instructions += [
        _lbz(4, 0, 30),                 # r4 = current level
        _cmplw(3, 4),
    ]
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "ble", "done"))
    instructions.append(_cmpwi(31, 0))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "beq", "done"))
    instructions.append(_addi(31, 31, -1))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "bl", PROCESS_LEVEL_UP))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "b", "loop"))
    labels["done"] = len(instructions)

    epilogue = [
        _lwz(0, 36, 1),
        _mtlr(0),
        _lwz(29, 20, 1),
        _lwz(30, 24, 1),
        _lwz(31, 28, 1),
        _addi(1, 1, 32),
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
        else:
            raise ValueError(f"unknown fill kind: {kind}")

    assert all(instr is not None for instr in instructions), \
        "unfilled branch placeholder remained in mechanic_progressive_leveling stub"

    patcher.write_code(stub_addr, instructions + epilogue)
    return stub_addr


def apply(patcher):
    # NOP the XP-sufficiency branch only - cutscene gate and max-level gate
    # (the other two ANDed conditions in ProcessLevelUp) stay fully intact.
    patcher.patch_word(XP_CHECK_BRANCH, 0x60000000)

    # NOP the original AddPlayerEXP -> ProcessLevelUp call site, so normal
    # combat XP gain can't also trigger a free level-up now that the XP
    # check itself is disabled.
    patcher.patch_word(ADD_PLAYER_EXP_CALL_SITE, 0x60000000)

    stub_addr = _build_stub(patcher)
    patcher.register_tick_mechanic(stub_addr)