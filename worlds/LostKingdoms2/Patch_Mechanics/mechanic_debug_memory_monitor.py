"""
DEBUG-ONLY memory monitor. Not a gameplay mechanic - a diagnostic tool for
watching the game's own heap allocator live, instead of waiting for an
allocation failure/crash to notice a leak. Intended to be applied
temporarily alongside mechanic_randomize_monsters.py while investigating
memory issues, then removed again once done.

The allocator itself (FUN_800f2ba0 = the real implementation behind
MemAlloc, FUN_800f2c9c = MEM_FREE - see mechanic_randomize_monsters.py's
own REAL_SAM_BUFFER_BASE docstring for MEM_FREE's own layout) is a classic
free-list allocator, confirmed via direct disassembly:

  memoryArenaHandle (0x802E9170) is an INDEX, not a pointer. The arena
  descriptor itself lives at DAT_802e97a0 + memoryArenaHandle*0xc (12
  bytes per descriptor): +4 is the FREE list's own head pointer, +8 is
  the ALLOCATED list's own head pointer. Both lists share the same node
  layout: +0 = prev, +4 = next, +8 = size (all within that node's own,
  variable-sized block, i.e. the node header IS the allocation itself,
  same as MEM_FREE's own param_2-0x1c/-0x20 header fields).

This mechanic walks BOTH lists every tick, summing each one's own total
size and counting its own nodes, then writes all four results to fixed,
always-live scratch addresses - watch these directly in Dolphin's memory
viewer (or a Cheat Engine-style live watch) rather than needing to break
on an allocation failure to notice something is wrong. A steadily
shrinking free total / growing allocated total / growing allocated count,
correlated against a specific in-game action (e.g. an enemy's projectile
attack, per the user's own report), is a direct, live signature of
exactly which action leaks and roughly how much each occurrence costs.

MEMORY_MONITOR_FREE_TOTAL_ADDR    - total bytes currently in the free list
MEMORY_MONITOR_FREE_COUNT_ADDR    - number of free-list nodes
MEMORY_MONITOR_ALLOC_TOTAL_ADDR   - total bytes currently in the allocated list
MEMORY_MONITOR_ALLOC_COUNT_ADDR   - number of allocated-list nodes

All four are 4-byte, big-endian words. Walk is capped at
MAX_WALK_ITERATIONS per list per tick as a safety net, in case the list
itself is ever corrupted (e.g. by a bug elsewhere) - without this, a
corrupted list with a cycle would hang the tick handler forever instead
of just producing a wrong-looking (but bounded) reading for one tick.
"""

MEMORY_ARENA_HANDLE_ADDR = 0x802E9170
# NOT the arena table's own base address - a POINTER VARIABLE (confirmed
# via the real init function, FUN_800f2d28: "DAT_802e97a0 = param_1;")
# whose STORED VALUE points to wherever the real table actually lives,
# set dynamically at init time. Must be dereferenced (one lwz) before
# adding the per-arena offset - an earlier version of this mechanic
# treated this address as the table's own direct base, which silently
# read/walked the wrong memory entirely (this pointer variable's own
# raw bytes, and whatever unrelated global happens to sit 4/8 bytes
# after it in memory - confirmed live: the "free list head" it computed
# was actually DAT_802e97a4, a totally different global holding the
# arena COUNT, not any kind of pointer at all).
ARENA_DESCRIPTOR_TABLE_PTR_ADDR = 0x802E97A0
ARENA_DESCRIPTOR_STRIDE = 0xC

MAX_WALK_ITERATIONS = 4000  # generous; a real, healthy list is a small
                            # fraction of this - only exists to bound a
                            # corrupted/cyclic list's own worst case


def _lwz(rD, offset, rA):
    return 0x80000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _stw(rS, offset, rA):
    return 0x90000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stwu(rS, offset, rA):
    return 0x94000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _li(rD, simm):
    return _addi(rD, 0, simm)


def _addi(rD, rA, simm):
    return 0x38000000 | (rD << 21) | (rA << 16) | (simm & 0xFFFF)


def _add(rD, rA, rB):
    return 0x7C000214 | (rD << 21) | (rA << 16) | (rB << 11)


def _mullw(rD, rA, rB):
    return 0x7C0001D6 | (rD << 21) | (rA << 16) | (rB << 11)


def _mflr(rD):
    return 0x7C0802A6 | (rD << 21)


def _mtlr(rS):
    return 0x7C0803A6 | (rS << 21)


def _cmpwi(rA, simm):
    return 0x2C000000 | (rA << 16) | (simm & 0xFFFF)


def _cmplwi(rA, uimm):
    return 0x28000000 | (rA << 16) | (uimm & 0xFFFF)


def _rlwinm(rA, rS, SH, MB, ME):
    return 0x54000000 | (rS << 21) | (rA << 16) | (SH << 11) | (MB << 6) | (ME << 1)


def _bne(from_addr, to_addr):
    return 0x40820000 | ((to_addr - from_addr) & 0xFFFC)


def _bgt(from_addr, to_addr):
    return 0x41810000 | ((to_addr - from_addr) & 0xFFFC)


def _beq(from_addr, to_addr):
    return 0x41820000 | ((to_addr - from_addr) & 0xFFFC)


def _bge(from_addr, to_addr):
    return 0x40800000 | ((to_addr - from_addr) & 0xFFFC)


def _b(from_addr, to_addr):
    return 0x48000000 | ((to_addr - from_addr) & 0x3FFFFFC)


def _emit_load_addr(instructions, reg, addr):
    hi = (addr >> 16) & 0xFFFF
    lo = addr & 0xFFFF
    instructions.append(0x3C000000 | (reg << 21) | hi)          # lis reg, hi
    instructions.append(0x60000000 | (reg << 21) | (reg << 16) | lo)  # ori reg, reg, lo


def _emit_walk_list(instructions, fills, labels, tag, list_ptr_reg,
                     total_out_addr, count_out_addr):
    """
    Walks the linked list whose head is already in list_ptr_reg (a node
    address, or 0). Sums each node's own size (+8) and counts nodes,
    writing both results to the given fixed addresses. Clobbers
    r4-r9. Does not preserve list_ptr_reg's own register across this call
    (caller should treat it as scratch afterward).
    """
    total_reg, count_reg, cur_reg = 6, 7, 8

    instructions.append(_li(total_reg, 0))
    instructions.append(_li(count_reg, 0))
    instructions.append(_addi(cur_reg, list_ptr_reg, 0))  # cur = list_ptr_reg (mr via addi rD,rA,0)
    instructions.append(_li(9, MAX_WALK_ITERATIONS))

    labels[f"{tag}_loop"] = len(instructions)
    instructions.append(_cmpwi(cur_reg, 0))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "beq", f"{tag}_done"))
    instructions.append(_cmpwi(9, 0))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "beq", f"{tag}_done"))
    # Defensive sanity check, not just a null check: this stub runs every
    # tick via the dispatcher hook, including very early during level
    # load-in - confirmed live as a real crash (invalid read from a
    # tiny, obviously-garbage address like 0x9, PC landing inside this
    # exact stub) when the game's own memory allocator apparently wasn't
    # fully initialized yet at that point, making memoryArenaHandle (and
    # therefore this computed list-head/next pointer) garbage rather
    # than a real address. Reject anything that doesn't look like a
    # genuine GameCube RAM address before ever dereferencing it, treating
    # it the same as end-of-list rather than trusting the list blindly -
    # same defensive pattern already used in mechanic_progressive_
    # attributes.py's own .sam buffer fix.
    #
    # GameCube main RAM spans 0x80000000-0x817FFFFF (24MB), i.e. the top
    # byte is 0x80 OR 0x81 - NOT just 0x80. An earlier version of this
    # check only accepted exactly 0x80, which rejected genuinely valid
    # pointers into the upper half of RAM - confirmed live: a real,
    # active free-list head (0x815b3d60) got rejected outright, making
    # every watched value read as a static 0 forever, even though the
    # list itself was genuinely populated and active. Checking
    # (top_byte - 0x80) <= 1 via an UNSIGNED comparison accepts both
    # 0x80 and 0x81 while still rejecting everything else (a byte below
    # 0x80 wraps around to a huge unsigned value on subtraction, which
    # correctly fails the <=1 check too).
    instructions.append(_rlwinm(4, cur_reg, 8, 24, 31))  # top byte of cur_reg
    instructions.append(_addi(4, 4, -0x80))
    instructions.append(_cmplwi(4, 1))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "bgt", f"{tag}_done"))
    instructions.append(_addi(9, 9, -1))

    instructions.append(_lwz(4, 8, cur_reg))       # r4 = cur->size
    instructions.append(_add(total_reg, total_reg, 4))
    instructions.append(_addi(count_reg, count_reg, 1))
    instructions.append(_lwz(cur_reg, 4, cur_reg))  # cur = cur->next

    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "b", f"{tag}_loop"))
    labels[f"{tag}_done"] = len(instructions)

    _emit_load_addr(instructions, 4, total_out_addr)
    instructions.append(_stw(total_reg, 0, 4))
    _emit_load_addr(instructions, 4, count_out_addr)
    instructions.append(_stw(count_reg, 0, 4))


def _build_stub(patcher):
    global MEMORY_MONITOR_FREE_TOTAL_ADDR, MEMORY_MONITOR_FREE_COUNT_ADDR
    global MEMORY_MONITOR_ALLOC_TOTAL_ADDR, MEMORY_MONITOR_ALLOC_COUNT_ADDR

    MEMORY_MONITOR_FREE_TOTAL_ADDR = patcher.alloc_cave(4)
    MEMORY_MONITOR_FREE_COUNT_ADDR = patcher.alloc_cave(4)
    MEMORY_MONITOR_ALLOC_TOTAL_ADDR = patcher.alloc_cave(4)
    MEMORY_MONITOR_ALLOC_COUNT_ADDR = patcher.alloc_cave(4)
    for addr in (MEMORY_MONITOR_FREE_TOTAL_ADDR, MEMORY_MONITOR_FREE_COUNT_ADDR,
                 MEMORY_MONITOR_ALLOC_TOTAL_ADDR, MEMORY_MONITOR_ALLOC_COUNT_ADDR):
        patcher.patch_word(addr, 0)

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
    ]

    # r29 = arena descriptor address = *ARENA_DESCRIPTOR_TABLE_PTR_ADDR
    # (dereferenced - see that constant's own docstring above for why)
    # + memoryArenaHandle * ARENA_DESCRIPTOR_STRIDE
    _emit_load_addr(instructions, 3, MEMORY_ARENA_HANDLE_ADDR)
    instructions.append(_lwz(3, 0, 3))              # r3 = memoryArenaHandle (index)
    instructions.append(_li(4, ARENA_DESCRIPTOR_STRIDE))
    instructions.append(_mullw(3, 3, 4))            # r3 = handle * stride
    _emit_load_addr(instructions, 29, ARENA_DESCRIPTOR_TABLE_PTR_ADDR)
    instructions.append(_lwz(29, 0, 29))            # r29 = *ARENA_DESCRIPTOR_TABLE_PTR_ADDR (the real table base)
    instructions.append(_add(29, 29, 3))            # r29 = arena descriptor addr

    # Same defensive reasoning as _emit_walk_list's own top-byte check
    # (see its docstring) - r29 itself could already be garbage if
    # memoryArenaHandle wasn't valid yet (e.g. very early during level
    # load-in, before this tick's own dispatcher hook should really be
    # touching the memory system at all). Skip this entire tick's own
    # work rather than reading through it if it doesn't look like a
    # genuine RAM address - the four output values simply keep their
    # previous tick's own reading for one tick, which is harmless for a
    # live-watched debug value. Same 0x80-OR-0x81 range check as
    # _emit_walk_list's own (see its docstring for why exactly-0x80 was
    # wrong) - applied here too for consistency, since this arena
    # descriptor address could equally fall anywhere in valid RAM.
    instructions.append(_rlwinm(3, 29, 8, 24, 31))  # top byte of r29
    instructions.append(_addi(3, 3, -0x80))
    instructions.append(_cmplwi(3, 1))
    idx = len(instructions)
    instructions.append(None)
    fills.append((idx, "bgt", "skip_this_tick"))

    # Free list: head = *(arena+4)
    instructions.append(_lwz(30, 4, 29))            # r30 = free list head
    _emit_walk_list(instructions, fills, labels, "free", 30,
                     MEMORY_MONITOR_FREE_TOTAL_ADDR, MEMORY_MONITOR_FREE_COUNT_ADDR)

    # Allocated list: head = *(arena+8) - re-read r29 fresh from the stack
    # slot isn't needed since r29 itself was never clobbered by
    # _emit_walk_list (only r4/r6/r7/r8/r9/r30 are touched there).
    instructions.append(_lwz(30, 8, 29))            # r30 = allocated list head
    _emit_walk_list(instructions, fills, labels, "alloc", 30,
                     MEMORY_MONITOR_ALLOC_TOTAL_ADDR, MEMORY_MONITOR_ALLOC_COUNT_ADDR)

    labels["skip_this_tick"] = len(instructions)

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
        if kind == "b":
            instructions[idx] = _b(from_addr, stub_addr + labels[target] * 4)
        elif kind == "beq":
            instructions[idx] = _beq(from_addr, stub_addr + labels[target] * 4)
        elif kind == "bne":
            instructions[idx] = _bne(from_addr, stub_addr + labels[target] * 4)
        elif kind == "bgt":
            instructions[idx] = _bgt(from_addr, stub_addr + labels[target] * 4)
        else:
            raise ValueError(f"unknown fill kind: {kind}")

    assert all(instr is not None for instr in instructions), \
        "unfilled branch placeholder remained in mechanic_debug_memory_monitor stub"

    patcher.write_code(stub_addr, instructions + epilogue)
    return stub_addr


def apply(patcher):
    stub_addr = _build_stub(patcher)
    patcher.register_tick_mechanic(stub_addr)