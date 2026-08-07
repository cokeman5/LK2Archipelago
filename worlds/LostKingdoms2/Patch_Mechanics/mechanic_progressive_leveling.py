"""
Progressive leveling. Disables the game's own XP-based leveling entirely
and instead drives player level directly off progressive_leveling
(LK2Client.STORAGE_ADDRESSES, 0x8025e656) via a per-tick mechanic
registered with mechanic_per_tick_hook - the AP client writes the desired
level there, and this mechanic calls the game's own ProcessLevelUp
(0x80073674) repeatedly until playerLevel (0x8025d02c) catches up.

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

    instructions = [
        _stwu(1, -32, 1),
        _mflr(0),
        _stw(0, 36, 1),
        _stw(29, 20, 1),
        _stw(30, 24, 1),
        _stw(31, 28, 1),
        _lis(29, pl_hi),                # r29 = &progressive_leveling
        _ori(29, 29, pl_lo),
    ]
    # One-time baseline init: if progressive_leveling has never been set
    # (still 0), initialize it to PROGRESSIVE_LEVELING_BASELINE. Naturally
    # only takes effect once, since this value should only ever increase
    # afterward (AP-granted levels never decrease it back to 0).
    instructions += [
        _lbz(3, 0, 29),
        _cmpwi(3, 0),
        None,   # bne skip_init (filled below)
        _li(3, PROGRESSIVE_LEVELING_BASELINE),
        _stb(3, 0, 29),
    ]
    bne_init_idx = len(instructions) - 3
    skip_init_idx = len(instructions)

    instructions += [
        _lis(30, lvl_hi),               # r30 = &playerLevel
        _ori(30, 30, lvl_lo),
        _li(31, MAX_LEVEL_SAFETY_CAP),  # r31 = safety counter
    ]

    loop_idx = len(instructions)
    instructions += [
        _lbz(3, 0, 29),                 # r3 = desired level
    ]
    # Safety clamp: playerLevel can never exceed MAX_LEVEL (ProcessLevelUp's
    # own hard gate), so if the stored desired value is ever set above it,
    # "desired > current" would never become false - this would silently
    # burn through the full 20-iteration safety cap every single tick,
    # forever, looking like a freeze even though each individual tick does
    # terminate.
    instructions += [
        _cmpwi(3, MAX_LEVEL),
        None,   # ble skip_clamp (filled below)
        _li(3, MAX_LEVEL),
    ]
    skip_clamp_idx = len(instructions)

    instructions += [
        _lbz(4, 0, 30),                 # r4 = current level
        _cmplw(3, 4),
        None,   # ble done (filled below)
        _cmpwi(31, 0),
        None,   # beq done (filled below)
        _addi(31, 31, -1),
        None,   # bl ProcessLevelUp (filled below)
        None,   # b loop (filled below)
    ]
    done_idx = len(instructions)

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

    instructions[bne_init_idx] = _bne(stub_addr + bne_init_idx * 4, stub_addr + skip_init_idx * 4)
    instructions[loop_idx + 2] = _ble(stub_addr + (loop_idx + 2) * 4, stub_addr + skip_clamp_idx * 4)
    instructions[loop_idx + 6] = _ble(stub_addr + (loop_idx + 6) * 4, stub_addr + done_idx * 4)
    instructions[loop_idx + 8] = _beq(stub_addr + (loop_idx + 8) * 4, stub_addr + done_idx * 4)
    instructions[loop_idx + 10] = patcher.make_bl(stub_addr + (loop_idx + 10) * 4, PROCESS_LEVEL_UP)
    instructions[loop_idx + 11] = _b(stub_addr + (loop_idx + 11) * 4, stub_addr + loop_idx * 4)

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