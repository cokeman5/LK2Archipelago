"""
REVISION 14: the code cave this all lives in is only ~8KB, SHARED with
every other mechanic - REVISION 13's fully-unrolled approach (unique
code generated per swap, ~239 swaps) produced ~248KB, a ~30x overshoot,
and crashed patch generation outright (RuntimeError: code cave
exhausted). Micro-optimizing the old unrolled code could never close a
gap that large - the only real fix is architectural: SWAPS is no
longer turned into unique code per entry. Instead, it's packed into a
compact 17-byte-per-record binary table (see RECORD_STRUCT_FORMAT/
_pack_record() below), and BOTH hooks are now a single shared loop
(written ONCE) that walks that table at runtime, comparing each
record's own target_level_id against LEVEL_ID_ADDR's current value and
processing only the matches for whichever level is actually loading.
This replaces ~248KB with (as of this revision) roughly 4-7KB total -
still worth checking against whatever's actually left in the cave
alongside this APworld's other mechanics; if it's still too tight,
the number of levels/swaps covered (not just how efficiently each one
is encoded) is the next lever to pull.

Per-swap path STRINGS are gone too - donor_card_id/donor_level_id are
formatted into a handful of SHARED, reusable path template buffers at
runtime (format_digits(), a tiny subroutine using divwu/mullw/subf to
turn a number into zero-padded ASCII digits) rather than each swap
carrying its own static path string.

The old per-swap donor_addr_var_addr (one dedicated 4-byte cave slot
PER SWAP, so HOOK2 could read back whatever HOOK1 computed for that
exact swap) doesn't scale either. Since only one LEVEL's own subset of
records is ever "in flight" in a single patch execution, this shrinks
to donor_addr_scratch - an array sized to the LARGEST single level's
own swap count (8, as of this revision - NOT 239), with both hooks
independently maintaining their own running index into it. Getting
this right required care: the index must advance based purely on
"this record's own level matched", THE SAME CRITERION both hooks use,
claimed unconditionally right after the level check - NOT only on
HOOK1's own load actually succeeding (an early draft of this revision
only advanced the index on success, which desyncs HOOK1's and HOOK2's
own index sequences the moment any single record's load fails,
silently misapplying every subsequent record in that same level to
the wrong donor).

Registers still follow the same hard constraint established in prior
revisions: only r29/r30 (and LR, saved/restored the same way as
always) are empirically confirmed to survive the specific "bl" calls
made here - nothing else can be trusted to persist across a call to a
native game function. Since this revision needs an additional
persistent value (the current record pointer) that r29/r30 have no
room for (both are already committed to their own established,
overlapping uses within a single record's own processing), it lives
in memory instead (current_record_ptr_addr), reloaded via a small
helper (emit_load_field()) every time a field is needed rather than
kept live in any register across a call.

IMPORTANT: this is a substantially larger rewrite than prior
revisions, and unlike them, could not be validated against real
hardware/an emulator as part of this change - only static verification
was possible (instruction encoding validity, branch-displacement range
checks, self-targeting-branch scans, record round-trip packing tests).
Test carefully in-game before relying on this, ideally starting with a
save that visits a few different levels before trusting the full set.

REVISION 11: donors are no longer restricted to a single hardcoded
level file (s17.pds) - the donor pool now draws from EVERY monster in
monster_database.py with at least one confirmed native_levels entry
(any level, not just s17.pds), and each swap loads its own donor from
whichever level file that donor actually lives in (its own
donor_level_file, picked per-swap - see apply()). This meant the
formerly-shared, single DONOR_LEVEL_PATH cave allocation (one path for
every swap, since every donor used to come from s17.pds) had to become
a per-swap allocation instead (swap["donor_path_addr"]), since two
swaps in the same patch can now legitimately need to open two
different level files. Everything about HOW a single donor gets loaded
once its own path is resolved (DVDConvertPathToEntrynum -> DVDFastOpen
-> MemAlloc -> async read -> ...) is unchanged.

Note this also means a donor can legitimately come from s01.pds itself
(the level being patched) - e.g. Dark Raven, Beaker, Hell Hound,
Incubus, and Succubus themselves all have a confirmed s01.pds
native_levels entry (from this project's own extraction script run
against s01.pds), so any of them can be randomly selected as a donor
for a DIFFERENT native slot in the same patch, same as any other
monster in the pool. Reading a level file's own resource data via a
plain DVD offset read is unaffected by whether that same file is also
the level currently being loaded natively elsewhere.

REVISION 10: which donor each native slot gets is now chosen at random,
at patch time, instead of being hardcoded - build_random_donor_mapping()
computes a random 1:1 (bijective) assignment from this level's own
native monsters to the pool of currently-confirmed donors (see
monster_database.py), so no donor monster is ever assigned to more than
one native slot in a single patch. This runs inside apply() itself
(seeded via output_data["Seed"], following this APworld's existing
per-mechanic seed-offset convention - see apply()'s own random.seed()
call), so apply()'s own signature changed from apply(patcher) to
apply(patcher, output_data) - _apply_mechanics() in ISO_Patcher.py was
updated to match. SWAPS below now only expresses each native slot's own
address and which native monster occupies it - the donor assignment,
and everything about that donor (which level file it's sourced from,
where its data lives within that file, its own card ID, its own
confirmed sound ID), is resolved at the top of apply() and looked up
from the database via get_donor_data().

REVISION 9: donor/monster data (file offsets, sizes, card IDs, sound
IDs) moved out of this file entirely, into a single shared source of
truth - monster_database.py, in this same Patch_Mechanics package.
This is meant to scale to many more swaps, across many more levels,
without this file's own size growing much - see monster_database.py's
own docstring for the full schema.

Everything about HOW a single swap works is unchanged from the proven,
working revision 7/8 - two hook points inside
LoadLevelAndShowLoadingScreen (see HOOK_ADDR/HOOK2_ADDR below for the
full explanation of why two are needed), each running the same
sequence of steps (sound preload, texture preload, donor model data
load, and - at HOOK2 only, since HOOK1 runs before the native level
file's own monster-table processing and would otherwise get silently
overwritten - the actual word[0]/DecodeResourcePoolCategory/word[8]
slot write), looped once per swap in SWAPS.

BUG FIX CARRIED FORWARD FROM REVISION 8: the three ctm-load failure-path
blocks (open/memalloc/read-start failed) must never be placed
IMMEDIATELY after a label with zero instructions preceding it (e.g.
directly after {tag}_texture_skip's own label) - doing so once made two
labels resolve to the identical index, so that block's own "b"
instruction branched to itself and hung forever (confirmed via direct
in-game testing on the very first swap processed). They're deliberately
placed after the model-load sequence's own failure paths instead, where
real instructions always precede each label.

REVISION 13: SWAPS is no longer a small, hand-curated list scoped to
s01.pds - it's now built by _build_swaps_from_native_slots() from
EVERY entry in monster_database.py's own NATIVE_SLOTS, across every
level populated there (49 levels as of this revision, ~239 native
slots total). target_level_id is no longer a small hardcoded lookup
table either - _infer_level_id() derives it directly from a level
file's own name (sNN.pds -> NN), since the project owner confirmed
this game's own level numbering IS the file name (regular levels
1-69, VS-mode arenas 90-95), validated against those ranges rather
than trusted blindly. HOOK1/HOOK2's own per-target-level-group gating
(see _group_swaps_by_target_level(), added in REVISION 12) is what
makes this scale cleanly - adding a level to monster_database.py's own
NATIVE_SLOTS is now the ONLY step needed to have that level's own
monsters randomized too, no code changes anywhere in this file.

IMPORTANT CAVEAT CARRIED FORWARD: almost every entry in
monster_database.py's own NATIVE_SLOTS is an unverified PREDICTION
(predicted_slot_addr = 0x80238e18 + table_index * 0x24), not
independently confirmed live data - only s01.pds's own Beaker and Dark
Raven slots are. The project owner has explicitly chosen to accept
this tradeoff (broad, immediate coverage across every scanned level,
at the cost of some slots possibly being wrong) rather than confirm
each level individually first. If a specific level's own swap looks
wrong in-game, that level's own predicted addresses in
monster_database.py are the first thing to check.

REVISION 12 CORRECTION: post-boss monster 1/2's own native occupants
(in s01.pds) were previously recorded backwards (post_boss_1=Incubus,
post_boss_2=Succubus). Direct inspection of s01.pds's own raw monster
table (uploaded and checked byte-for-byte) shows its own on-disk
order is Beaker, Dark Raven, Hell Hound, Succubus, Incubus - table
positions 0-2 match the two directly-confirmed slots plus Hell Hound's
own assumed slot exactly, in order, which is strong evidence that
on-disk table order equals RAM slot order in general (this is exactly
the assumption REVISION 13's own predicted NATIVE_SLOTS data rests
on). That same order puts Succubus, not Incubus, at position 3 and
Incubus at position 4 - monster_database.py's own NATIVE_SLOTS was
corrected accordingly. Worth an in-game check to be certain, since
this still isn't independently confirmed live the way Dark Raven's
own slot was.

As of this revision, the donor pool has 196 confirmed monsters (every
card_id in monster_database.py with at least one native_levels entry
and a confirmed sound_id). SWAPS has 239 entries (one per (level,
slot) occurrence), but only 196 DISTINCT native card_ids appear across
them - 39 species natively recur in more than one level - and that set
of 196 distinct native species turns out to be EXACTLY the 196-monster
donor pool itself. So donor assignment is a true global bijection at
the species level (build_random_donor_mapping() runs once, over
distinct_native_card_ids, not once per slot or per level) - every
donor is used exactly once, anywhere in the game, and every occurrence
of a given native species (across every level it naturally appears in)
consistently becomes that same one donor. As more donors/native slots
get confirmed in monster_database.py, both pools grow together - no
changes needed here.

The very first two-hook, single-swap version, and the first
generalized-but-not-yet-database-backed multi-swap version, are both
preserved in prior outputs of this same file - see project history if
needed as reference.
"""

import logging
import random
import re
import struct

from . import monster_database as db

logger = logging.getLogger()  # root logger, matching ISO_Patcher.py's own convention

# Every level's own numeric ID (the byte LEVEL_ID_ADDR holds during
# loading - the same index BuildKnownCardList/QueueAsyncFileLoad's own
# (&DAT_80205af0)[levelId] array uses) is simply the "NN" in that
# level's own file name (e.g. s17.pds -> 17) - confirmed directly by
# the project owner, who has full knowledge of this game's own level
# numbering (regular levels 1-69, VS-mode arenas 90-95). No lookup
# table is needed - this is a formula, not per-level data.
_LEVEL_FILENAME_RE = re.compile(r"^s(\d+)\.pds$", re.IGNORECASE)


def _infer_level_id(level_file):
    """Derives a level file's own numeric level ID directly from its
    own file name (sNN.pds -> NN), validating it falls within a known
    real range (regular levels 1-69, VS-mode arenas 90-95) rather than
    trusting an arbitrary parsed number blindly - a file that doesn't
    match this game's own real numbering would otherwise silently
    produce a plausible-looking but wrong ID."""
    match = _LEVEL_FILENAME_RE.match(level_file)
    if not match:
        raise ValueError(f"{level_file!r} doesn't match the expected 'sNN.pds' naming pattern - can't infer its own level ID")
    level_id = int(match.group(1))
    if not (1 <= level_id <= 69 or 90 <= level_id <= 95):
        raise ValueError(f"{level_file!r} -> inferred level ID {level_id} is outside the known valid ranges (1-69, 90-95)")
    return level_id


def _slugify(name):
    """Lowercase, underscore-separated version of a monster's own display
    name, for use in generated tag/label strings (e.g. "Will 'o wisp" ->
    "will_o_wisp"). These tags only need to be unique strings, not valid
    Python identifiers, but keeping them readable helps when reading
    logs/disassembly."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# --- Diagnostic exclusion (REVISION 20): confirmed via direct testing
# that a level 7 cutscene crashes 100% reproducibly, only with this
# mechanic active, unrelated to any leak (happens on a fresh save
# visiting only level 1 and level 7). Leading theory: the cutscene
# hard-references specific animation/texture data belonging to one of
# s07.pds's own NATIVE monsters, which a random donor doesn't
# replicate (different texture count/resource layout), causing an
# out-of-bounds reference when the cutscene tries to use it.
#
# EXCLUDED_LEVELS: level files pulled out of randomization ENTIRELY -
# every native monster in that level stays home, unswapped.
# EXCLUDED_SLOTS: individual (level_file, slot_addr) pairs pulled out
# instead, for narrowing down which specific slot is the actual
# culprit once whole-level exclusion confirms the crash goes away.
# Both empty by default - populate one or the other for bisection
# testing, then narrow down to the minimal fix before a real release
# (whole-level exclusion is a safe fallback if a specific slot can't
# be cleanly identified, at the cost of that level never getting
# randomized). EXCLUDED_NATIVE_CARD_IDS (below) is a separate,
# currently-populated exclusion by monster identity rather than by
# level/slot location.
EXCLUDED_LEVELS = set()
EXCLUDED_SLOTS = set()

# EXCLUDED_NATIVE_CARD_IDS: specific monsters (by card_id) hard-mapped
# to THEMSELVES as their own donor, rather than participating in the
# normal random donor assignment - they still go through the exact
# same donor-loading pipeline as every other swap (see apply()'s own
# comment near where this is used), just always ending up as a no-op
# in terms of which monster actually appears. Also removed from the
# general donor pool, so no OTHER slot can be randomized into becoming
# one of these either.
#
# NOTE: an earlier version of this fix instead skipped these monsters'
# own swaps entirely (leaving them truly unswapped/vanilla) - that was
# WRONG and caused a real crash: native-memory-reuse pools an entire
# contiguous run's own space together, so a skipped monster's own
# still-vanilla data could get silently overwritten by a NEIGHBORING
# swap's donor write within the same run, since the run's own total
# capacity accounting didn't know to leave that specific slot alone.
# Self-mapping avoids this entirely, since the donor's own file_offset/
# size is then IDENTICAL to the native slot's, by construction.
#
# TEMPORARY - Gargoyle (0xca), Horus (0xcf), and Black Dragon (0x40)
# excluded while investigating an issue involving them, all three
# native to s13.pds (Black Dragon is also native to s68.pds - excluded
# from randomization there too, since exclusion is per-card_id, not
# per-level).
# (Note: 0x4d is "Fire Gargoyle," a DIFFERENT monster native to
# s27.pds - an earlier version of this set mistakenly used 0x4d
# instead of the correct 0xca; corrected.)
EXCLUDED_NATIVE_CARD_IDS = {0xca, 0xcf, 0x40}


def _build_swaps_from_native_slots():
    """
    Builds the full SWAPS list from db.NATIVE_SLOTS - one swap per
    (level, slot_addr, native_card_id) entry found there, across every
    level currently populated, not just s01.pds. Only each slot's own
    address, native occupant, and target level are fixed here - WHICH
    donor it gets is assigned randomly, per-generation, inside apply()
    (see build_random_donor_mapping() below). Once assigned, the
    donor's own data (which level file it's sourced from, where it
    lives within that file, its own card ID, its own confirmed sound
    ID) is looked up from monster_database via get_donor_data().
    get_donor_data() raises clearly (see its own docstring) if a card
    ID is "special" (above MAX_NORMAL_CARD_ID) or hasn't been confirmed
    as a usable donor from that level yet - so an unconfirmed card
    ending up in the random pool would fail loudly at patch time, not
    silently at runtime.

    IMPORTANT: db.NATIVE_SLOTS is mostly UNVERIFIED, PREDICTED data -
    see its own docstring in monster_database.py. The project owner has
    explicitly accepted this tradeoff (broad coverage now, at the cost
    of some slots possibly being wrong) rather than confirming each
    level individually via live memory tracing first.

    EXCLUDED_LEVELS/EXCLUDED_SLOTS (below) let specific levels or
    specific slots be pulled out of randomization entirely (that
    native monster just stays home, unswapped) - added for bisecting
    a level-7 crash, confirmed tied to a cutscene that hard-references
    a specific native monster's own animation/texture data in a way a
    random donor doesn't satisfy. Toggle these to isolate which slot
    is the actual culprit: start with the whole level excluded to
    confirm the crash goes away, then narrow to individual slot
    addresses (comment/uncomment in EXCLUDED_SLOTS) one at a time.
    """
    swaps = []
    for level_file in sorted(db.NATIVE_SLOTS.keys()):
        if level_file in EXCLUDED_LEVELS:
            continue
        slots = db.NATIVE_SLOTS[level_file]
        slot_position = 0  # kept as internal bookkeeping only (not packed into records - see REVISION 24 note below)
        for slot_addr in sorted(slots.keys()):
            if (level_file, slot_addr) in EXCLUDED_SLOTS:
                continue
            native_card_id = slots[slot_addr]
            if not isinstance(native_card_id, int):
                raise ValueError(
                    f"db.NATIVE_SLOTS[{level_file!r}][{hex(slot_addr)}] is {native_card_id!r}, "
                    f"not a valid card_id (int) - monster_database.py's own NATIVE_SLOTS is stale "
                    f"or was hand-edited incorrectly. Every entry needs a real card_id; if this "
                    f"level's own native occupant genuinely isn't known yet, remove the entry "
                    f"entirely rather than leaving a None/placeholder value, since this mechanic "
                    f"has no meaningful way to swap a slot whose own native occupant is unknown."
                )
            native_name = db.get_monster(native_card_id)["name"]
            swaps.append({
                "name": f"{_slugify(level_file)}_{_slugify(native_name)}",
                "target_slot_addr": slot_addr,
                "native_card_id": native_card_id,
                "target_level_file": level_file,
                "slot_position": slot_position,
            })
            slot_position += 1
    return swaps


SWAPS = _build_swaps_from_native_slots()


def _find_contiguous_native_runs(level_file):
    """
    REVISION 26: identifies maximal runs of NATIVE_SLOTS-tracked
    monsters within level_file whose own [file_offset, file_offset+size)
    ranges are VERIFIED, BYTE-EXACT CONTIGUOUS - i.e., monster B's own
    offset equals monster A's own offset+size exactly, with NOTHING
    else (tracked or not) able to fit between them. This is the safety
    foundation for REVISION 26's own memory-reuse scheme (see apply()'s
    own docstring note): since every native monster is swapped 100% of
    the time, and DecodeResourcePoolCategory already ran natively for
    all of them before any of our own hooks execute, a VERIFIED
    contiguous run's own total space is safe to reuse for donor data in
    any order - but this must NEVER be assumed across a gap, since
    db.NATIVE_SLOTS is known to not track every monster physically
    present in every level (confirmed directly: s02.pds has 7 real
    monster entries in its own file but only some are in NATIVE_SLOTS,
    and the untracked one(s) are NOT being swapped, meaning their own
    data is very much still in use). A gap boundary is therefore a hard
    wall - never pooled across, no matter how tempting the numbers look
    - because an untracked, still-needed monster could be sitting right
    there. Returns a list of runs; each run is its own list of
    (card_id, file_offset, size) tuples, sorted by file_offset.
    """
    entries = []
    for slot_addr, card_id in db.NATIVE_SLOTS[level_file].items():
        monster = db.MONSTERS.get(card_id)
        lvl_data = monster["native_levels"].get(level_file) if monster else None
        if lvl_data:
            entries.append((lvl_data["file_offset"], lvl_data["size"], card_id))
    entries.sort()

    runs = []
    current_run = []
    prev_end = None
    for file_offset, size, card_id in entries:
        if prev_end is not None and file_offset != prev_end:
            runs.append(current_run)
            current_run = []
        current_run.append((card_id, file_offset, size))
        prev_end = file_offset + size
    if current_run:
        runs.append(current_run)
    return runs


def _build_run_table_and_assign_run_ids():
    """
    Builds the single, GLOBAL run table (shared cave data, one small
    entry per run across every level - see REVISION 26's own note in
    apply()) and assigns each SWAP its own run_id (an index into that
    table). A run_id is only meaningful in combination with the swap's
    own target_level_id - the SAME run_id space is shared across all
    levels (no separate per-level indexing needed), since only the
    CURRENT level's own runs are ever consulted at runtime anyway.
    """
    run_table = []  # list of (start_offset, total_size)
    card_id_to_run_id = {}  # (level_file, card_id) -> run_id
    for level_file in sorted(db.NATIVE_SLOTS.keys()):
        if level_file in EXCLUDED_LEVELS:
            continue
        for run in _find_contiguous_native_runs(level_file):
            run_id = len(run_table)
            start_offset = run[0][1]
            total_size = sum(size for _, _, size in run)
            run_table.append((start_offset, total_size))
            for card_id, _, _ in run:
                card_id_to_run_id[(level_file, card_id)] = run_id

    for swap in SWAPS:
        key = (swap["target_level_file"], swap["native_card_id"])
        swap["run_id"] = card_id_to_run_id.get(key)  # None if excluded/untracked - handled at runtime as "no reuse available"

    return run_table


RUN_TABLE = _build_run_table_and_assign_run_ids()

DVD_SECTOR_SIZE = 0x800  # 2048 bytes

# --- REVISION 28: re-applying REVISION 27's own donor-table
# indirection, now that it's been CONFIRMED SAFE - the level 2 crash
# persisted with this refactor both present AND fully reverted, ruling
# it out as the cause. Re-applying it purely to reclaim cave space.
#
# donor_card_id/donor_level_id/donor_sound_id/donor_file_offset/
# donor_size are all FUNDAMENTALLY PER-DONOR properties (fixed once a
# card is picked as a donor), not per-swap-occurrence ones - and since
# the donor bijection is per-SPECIES, not per-occurrence, the same
# donor gets reused across every level that species natively appears
# in (239 total swap occurrences, but only 196 distinct donors are
# ever actually used). They live in DONOR_TABLE (one shared, 12-byte
# entry per distinct donor actually used); each record carries only a
# 1-byte donor_pool_index into it.
#
# REVISION 31: target_slot_addr replaced with table_index - every
# swap's own target_slot_addr is SLOT_BASE_ADDR + table_index *
# SLOT_STRIDE (confirmed: table_index fits a u8 for all 239 swaps,
# max needed is 9), so storing the raw computed address (4 bytes) was
# genuinely wasteful - the runtime now derives it from a 1-byte index
# via a single multiply-add. Saves ~717 bytes (3 bytes x 239 records).
#
# Each record is exactly 4 bytes, big-endian, struct format ">BBBB" -
# no padding (PPC integer loads dont require alignment):
#   +0x00 (1 byte,  u8 ) table_index          (target_slot_addr = SLOT_BASE_ADDR + table_index*SLOT_STRIDE)
#   +0x01 (1 byte,  u8 ) target_level_id
#   +0x02 (1 byte,  u8 ) donor_pool_index     (index into DONOR_TABLE)
#   +0x03 (1 byte,  u8 ) native_run_id        (REVISION 26: 0xFF = no verified-safe run available)
RECORD_STRUCT_FORMAT = ">BBBB"
RECORD_SIZE = struct.calcsize(RECORD_STRUCT_FORMAT)
assert RECORD_SIZE == 4

REC_TABLE_INDEX = 0x00          # u8
REC_TARGET_LEVEL_ID = 0x01      # u8
REC_DONOR_POOL_INDEX = 0x02     # u8
REC_NATIVE_RUN_ID = 0x03        # u8

SLOT_BASE_ADDR = 0x80238e18
SLOT_STRIDE = 0x24

# DONOR_TABLE entry layout - one shared 12-byte entry per distinct
# donor actually used, struct format ">BBHII":
#   +0x00 (1 byte,  u8 ) donor_card_id
#   +0x01 (1 byte,  u8 ) donor_level_id
#   +0x02 (2 bytes, u16) donor_sound_id
#   +0x04 (3 bytes, u24) donor_file_offset   (REVISION 32: shrunk from u32 - max real value ~3.75MB,
#                                              comfortably under the 16MB u24 ceiling. Safe to read at
#                                              runtime as "load a word starting 1 byte early, mask off
#                                              the top byte" since donor_sound_id's own last byte
#                                              immediately precedes this field - never reads before the
#                                              start of the entry.)
#   +0x07 (3 bytes, u24) donor_size          (REVISION 32: same reasoning - max real value ~412KB.
#                                              Reading 1 byte early safely borrows from
#                                              donor_file_offset's own last byte instead.)
DONOR_TABLE_ENTRY_FORMAT = ">BBH"  # only the fixed-width prefix - the two u24 fields are packed manually
DONOR_TABLE_ENTRY_SIZE = struct.calcsize(DONOR_TABLE_ENTRY_FORMAT) + 3 + 3
assert DONOR_TABLE_ENTRY_SIZE == 10

DTE_DONOR_CARD_ID = 0x00       # u8
DTE_DONOR_LEVEL_ID = 0x01      # u8
DTE_DONOR_SOUND_ID = 0x02      # u16
DTE_DONOR_FILE_OFFSET = 0x04   # u24
DTE_DONOR_SIZE = 0x07          # u24

NO_RUN_AVAILABLE = 0xFF


def _pack_u24(value):
    """Big-endian, 3-byte unsigned encoding - struct.pack has no native
    u24 type, so this just takes the low 3 bytes of a standard 4-byte
    big-endian encoding."""
    assert 0 <= value < 0x1000000, f"value {hex(value)} does not fit in 24 bits"
    return struct.pack(">I", value)[1:]


def _pack_record(swap):
    table_index = (swap["target_slot_addr"] - SLOT_BASE_ADDR) // SLOT_STRIDE
    assert 0 <= table_index <= 255, f"table_index {table_index} out of u8 range for {swap['name']}"
    return struct.pack(
        RECORD_STRUCT_FORMAT,
        table_index,
        swap["target_level_id"],
        swap["donor_pool_index"],
        swap["run_id"] if swap["run_id"] is not None else NO_RUN_AVAILABLE,
    )


def _pack_donor_table_entry(donor_entry):
    return (
        struct.pack(
            DONOR_TABLE_ENTRY_FORMAT,
            donor_entry["donor_card_id"],
            donor_entry["donor_level_id"],
            donor_entry["donor_sound_id"],
        )
        + _pack_u24(donor_entry["donor_file_offset"])
        + _pack_u24(donor_entry["donor_size"])
    )


def _compute_read_params(file_offset, size):
    """
    Sector-align a donor's own [file_offset, file_offset+size) range for
    DVD reading - not just 32-byte aligned, but 2048-byte (DVD sector)
    aligned, per the hard-won lesson from this project's own early
    revisions (see prior mechanic_cross_level_monster_poc.py history for
    the full "why" - trivially offset=0 reads always worked, but a
    genuinely mid-sector offset needed this rounding to read correctly).
    """
    aligned_offset = (file_offset // DVD_SECTOR_SIZE) * DVD_SECTOR_SIZE
    prefix = file_offset - aligned_offset
    end = file_offset + size
    aligned_end = ((end + DVD_SECTOR_SIZE - 1) // DVD_SECTOR_SIZE) * DVD_SECTOR_SIZE
    return aligned_offset, aligned_end - aligned_offset, prefix


def build_random_donor_mapping(native_card_ids, donor_pool_card_ids, rng):
    """
    Randomly assigns each entry in native_card_ids a distinct donor from
    donor_pool_card_ids - a random 1:1 (bijective) mapping, so no donor
    monster is ever assigned to more than one native slot in the same
    generation. A native monster CAN end up mapped to itself (i.e. a
    no-op "swap") - that's fine, just treated as any other outcome.

    native_card_ids: sequence of DISTINCT native monster card_ids that
        each need a donor assigned.
    donor_pool_card_ids: sequence of DISTINCT eligible donor card_ids
        (must have at least as many entries as native_card_ids).
    rng: a random.Random instance, or the random module itself - passed
        in rather than seeded internally, so the caller stays in control
        of seeding/determinism (see apply()'s own random.seed() call).

    Returns: dict {native_card_id: donor_card_id}

    REMOVED (per explicit request): an earlier version of this function
    rejected/repaired any assignment where a donor's own resolved
    native level matched a level the native monster was itself native
    to, based on a hypothesis (DVD/file-handle contention) that turned
    out not to be the actual root cause of the reported audio issue -
    the real fix ended up being elsewhere (HOOK2's own direct sound
    loading). Reverted to a plain, unconstrained shuffle.
    """
    native_card_ids = list(native_card_ids)
    remaining_donors = list(donor_pool_card_ids)

    if len(remaining_donors) < len(native_card_ids):
        raise ValueError(
            f"donor pool has only {len(remaining_donors)} eligible monster(s), "
            f"but {len(native_card_ids)} native slot(s) each need a distinct donor - "
            f"confirm more donors in monster_database.py first."
        )

    rng.shuffle(remaining_donors)
    chosen_donors = remaining_donors[:len(native_card_ids)]
    return dict(zip(native_card_ids, chosen_donors))


def _group_swaps_by_target_level(swaps):
    """
    Groups swaps by their own target_level_id, preserving first-seen
    order - lets HOOK1/HOOK2 gate each group independently (compare
    LEVEL_ID_ADDR's own byte against THIS group's own level_id, fall
    through to the next group's own check on a mismatch). SWAPS is now
    generated from db.NATIVE_SLOTS across every level populated there
    (see _build_swaps_from_native_slots()), so this typically produces
    dozens of groups, not one - grouping still just works, no code
    change needed as more levels get added to monster_database.py.

    Returns: list of (level_id, [swap, ...]) tuples, in first-seen order.
    """
    groups = {}
    order = []
    for swap in swaps:
        level_id = swap["target_level_id"]
        if level_id not in groups:
            groups[level_id] = []
            order.append(level_id)
        groups[level_id].append(swap)
    return [(level_id, groups[level_id]) for level_id in order]

LEVEL_ID_ADDR = 0x80209262  # byte holding the currently-loading level's own numeric ID - see _infer_level_id() above

# --- REVISION 32: HOOK1/HOOK_ADDR is no longer installed at all - kept
# here as historical reference only (both constants below are now
# unused by any active code). Originally installed immediately after
# LoadLevelAndShowLoadingScreen's own "QueueAsyncFileLoad(3, (&DAT_
# 80205af0)[levelId], 0, BuildKnownCardList)" call - but once sound,
# file_buffer/donor model data, and CTM/texture loading all moved to
# HOOK2 (each for its own, independent timing reason - see each
# section's own comment near HOOK2 for specifics), nothing this hook's
# own loop computed was still consumed anywhere; HOOK2 already,
# independently recomputes every one of those same values itself. The
# native instruction this address originally held (`lwz r0, -0x5380
# (r2)`, loading DAT_802eca40) is left completely untouched now, since
# nothing patches this address anymore at all. ---
HOOK_ADDR = 0x800533A4  # unused - see REVISION 32 note above
ORIGINAL_HOOK_INSTRUCTION = 0x8002AC80  # unused - see REVISION 32 note above

# --- Hook point 2: LoadLevelAndShowLoadingScreen's own while loop (which
# drains the native async queue, including the level file's own
# completion handler, FixupLevelSceneData) directly overwrites every
# native monster's own slot (word[0], via FixupLevelSceneData's own
# LoadAllLevelDataBlocks((uint*)&DAT_802092d0,&DAT_80236358) call - the
# same base array every target_slot_addr above belongs to) - confirmed
# by direct in-game testing: our own slot write from HOOK_ADDR (which
# runs BEFORE this while loop even starts) gets silently clobbered once
# the loop actually processes the level file, restoring every native
# monster's own, original data. HOOK2_ADDR is the instruction
# immediately following the while loop's own exit check (confirmed via
# direct disassembly: `lbz r0,-0x6da0(r3)` reading DAT_80209260,
# `cmplwi r0,0x10`, then a bc back to the loop's own continuation
# point) - i.e. the very first instruction that runs only once ALL
# native level-loading (including FixupLevelSceneData) is guaranteed
# complete, but still before InitEntity spawns the player. We re-apply
# every swap's own word[0]/DecodeResourcePoolCategory/word[8] slot
# write here - this time it sticks, since nothing runs after it to
# overwrite it again.
HOOK2_ADDR = 0x80053648
ORIGINAL_HOOK2_INSTRUCTION = 0x3C608021  # lis r3, 0x8021 - relocated, executed at the very end of our second stub

# --- Hook point 3 (REVISION 16): the real level-exit point, found in
# main()'s own compiled loop, not LoadLevelAndShowLoadingScreen at all.
# UpdateGameplayFrame() only returns once the player leaves/completes
# the level; right after it returns, main() runs a fixed cleanup
# sequence (EmptyLevelInitCallback, FreeAllCardCachedResources,
# FreeModelCacheSlots, DeactivateAllEntities, FreeAllLoadedDataBlocks,
# FreeLevelResources, CleanupLevelExtraDataBlocks, ...) before looping
# back around to load whatever's next - confirmed via direct
# disassembly: EXIT_HOOK_ADDR is the "bl DeactivateAllEntities"
# instruction itself (0x480006AD), immediately followed by "bl
# FreeAllLoadedDataBlocks" at EXIT_HOOK_ADDR+4 - i.e. the very start of
# that cleanup sequence, running exactly once per level visit, no
# matter how the player left (completed it, backed out, etc.), since
# DeactivateAllEntities/FreeAllLoadedDataBlocks are each called from
# nowhere else in the entire game. Unlike HOOK_ADDR/HOOK2_ADDR's own
# original instructions (both position-independent - a plain load and
# a lis - so relocating their raw bytes to run at the end of our own
# stub works fine), this hook's own original instruction is a RELATIVE
# branch (bl), which is NOT position-independent - relocating its raw
# bytes elsewhere would branch to the wrong place. So instead of
# relocating it, we reconstruct an equivalent call: our own stub ends
# with a plain "b" (not "bl") to DeactivateAllEntities' own real,
# decoded target address (DEACTIVATE_ALL_ENTITIES_ADDR) - a tail call,
# not a nested call, so LR is left exactly as the ORIGINAL "bl
# stub_addr" from main() itself set it (pointing at EXIT_HOOK_ADDR+4,
# i.e. the very next instruction, "bl FreeAllLoadedDataBlocks") -
# meaning DeactivateAllEntities' own "blr" naturally returns exactly
# where the original, unhooked code would have, with zero disruption
# to main()'s own control flow.
EXIT_HOOK_ADDR = 0x80055C98
DEACTIVATE_ALL_ENTITIES_ADDR = 0x80056344  # decoded from the original "bl DeactivateAllEntities" instruction's own relative displacement

# --- FUN_80130ce8 native bugfix (unrelated to the HOOK/HOOK2/EXIT_HOOK
# trio above - a direct, single-instruction patch to an EXISTING
# native function, not one of our own additive hook points).
#
# FUN_80130ce8(short sound_id) walks a native, per-level table
# (&DAT_802d7750, DAT_802e9ba2 groups) mapping specific sound_ids to
# an associated bone/joint-linked visual effect. Read directly, its
# own logic has no "not found" case at all: whether the table is
# empty (DAT_802e9ba2==0, checked before the search loop even starts)
# or the search loop runs through every group without ever matching
# sound_id, execution falls straight through to LAB_80130d5c and
# dereferences the search result (r31) unconditionally - r31 is only
# ever set to a valid pointer along the "found" path, staying at its
# own initial value (0) otherwise. This is not a data-completeness gap
# we can patch around by feeding it different values in our own,
# separate sound-slot struct (an earlier version of this fix tried
# exactly that, repeatedly, and it never worked - the crash PCs never
# once changed across four separate, increasingly-targeted attempts,
# which in hindsight was itself strong evidence those attempts were
# never actually in the failing path). This table is native, per-level
# data that was only ever built to include sound_ids belonging to
# monsters natively assigned to a given level - every sound_id vanilla
# gameplay ever passes to this function already, by construction,
# belongs in it. Our mechanic is the first thing that ever calls this
# same function with a donor's own sound_id, one genuinely foreign to
# the current level's own table - a case the native code was simply
# never written to expect, not a bug independent of our own mechanic.
#
# Fixed via a single-instruction trampoline hook at LAB_80130d5c itself
# (the crash label, and NOT a dedicated hook point - this instruction
# is patched IN PLACE, replaced with a same-size branch, so nothing
# after it in main.dol shifts at all): checks r31 for null before
# using it. If null (came from either "not found" path), branches
# directly to this same function's own, existing, already-correct
# epilogue (which restores r31/lr/r1 from the stack and returns) -
# skipping the unsafe body entirely. If non-null (a real match was
# found, the one path that already worked correctly natively),
# re-executes the original, displaced instruction and resumes normal
# execution exactly where it left off. Strictly safer than the
# existing behavior for ANY caller, native or ours, since a native
# call that happened to hit this same "not found" case would already
# crash identically today, with or without our own mechanic installed
# at all.
FUN_80130CE8_CRASH_LABEL_ADDR = 0x80130d5c   # lhz r0, 2(r31) - the instruction being replaced
FUN_80130CE8_RESUME_ADDR = 0x80130d60         # the very next instruction - branch back here after re-executing the above
FUN_80130CE8_SAFE_EPILOGUE_ADDR = 0x80130dac  # lwz r31,28(r1) - this function's own, existing, unmodified epilogue

# --- FUN_8012fda0 native bugfix (also unrelated to the HOOK/HOOK2/
# EXIT_HOOK trio - a second, separate single-instruction patch to an
# EXISTING native function).
#
# The actual, unified root cause behind BOTH this crash and the
# FUN_80130ce8 one fixed above - confirmed by tracing forward from
# FUN_80139384 (which itself already handles "not found" gracefully,
# passing a NULL param_2 rather than crashing) into this function,
# which FUN_80139384 calls with that same, now-NULL value. This
# function maintains a shared, global, 256-entry sorted table
# (&DAT_802d2350) - and its own final step, on ANY successful
# insertion path, is "(&DAT_802d2350)[iVar4*2] = param_2;" -
# UNCONDITIONALLY storing whatever it was given, including a NULL
# "not found" value, as if it were a valid entity pointer, no check at
# all. That NULL doesn't crash here - it just sits in the shared
# table. It crashes later, in whatever OTHER, unrelated native code
# happens to read this same slot next expecting a real pointer -
# confirmed as the actual, common ancestor of two visibly very
# different-looking crashes (FUN_8013688c, a linked-list unlink
# routine, and FUN_8013abbc, a per-frame update routine) via each
# one's own callstack ultimately tracing to reads of this same,
# corrupted table.
#
# Fixed the same way as FUN_80130ce8 - a single-instruction trampoline,
# same size in as out, nothing after it shifts. This function's own
# prologue happens to set r31 = param_2 immediately, BEFORE
# EnterCriticalSection() is ever called - the very next instruction
# (FUN_8012FDA0_HOOK_ADDR) is replaced with a branch to a small stub:
# if r31 is null, unwind the small, partial stack frame the prologue
# has already built (restore the caller's own r31 and LR from exactly
# where the prologue just saved them) and return 0 - this function's
# own, existing "not found / table full" return value - WITHOUT ever
# entering the critical section, since we haven't reached that point
# yet. If r31 is non-null (a genuine, valid insertion), re-execute the
# displaced instruction and resume normally - the one path that
# already worked correctly natively is untouched.
FUN_8012FDA0_HOOK_ADDR = 0x8012fdb4    # stw r30, 8(r1) - the instruction being replaced
FUN_8012FDA0_RESUME_ADDR = 0x8012fdb8   # the very next instruction - branch back here after re-executing the above
FUN_8012FDA0_R31_SAVE_OFFSET = 12        # this function's own prologue: stw r31, 12(r1)
FUN_8012FDA0_LR_SAVE_OFFSET = 20         # this function's own prologue: stw r0, 20(r1) (LR, saved in the CALLER's frame)
FUN_8012FDA0_FRAME_SIZE = 16             # this function's own prologue: stwu r1, -16(r1)

# --- REVISION 18: LoadAndCacheAnimationTexture's own texture cache
# system (decoded from the decompiled source). CACHE_ENTRY_TABLE_ADDR
# is a fixed 1024-slot table (CACHE_ENTRY_STRIDE=0x3c bytes each);
# byte 0 of each entry marks it "in use" (nonzero) or free (0) - the
# function scans linearly for the first free slot every single call
# and NEVER resets one back to free anywhere we've found, meaning it's
# a genuinely finite, otherwise-never-recycled resource across a whole
# session. HASH_TABLE_ADDR is a separate 0x10000-entry table (4 bytes
# each) that LoadAndCacheAnimationTexture updates with "if this hash's
# own slot is still 0, set it to the cache entry just used" - a
# write-once-per-hash pattern that's never refreshed on a later call
# for the SAME hash, even if the earlier cache entry it points to gets
# reused/freed elsewhere. Both explain the "bugged texture on a
# donor's second load" symptom precisely: the stale hash entry from an
# earlier level visit keeps pointing at a cache slot whose own source
# data we've since freed. EXIT_HOOK resets both for every texture it
# frees, so the next load of that same donor gets a clean slot AND a
# correctly-refreshed hash entry, instead of leaking the slot forever
# and leaving a dangling hash reference behind.
CACHE_ENTRY_TABLE_ADDR = 0x801F47C0
CACHE_ENTRY_STRIDE = 0x3C
HASH_TABLE_ADDR = 0x801B47C0

DVD_CONVERT_PATH = 0x800F9760       # DVDConvertPathToEntrynum(char *path)
DVD_FAST_OPEN = 0x800F9A54          # DVDFastOpen(entryNum, fileInfo*)
ASYNC_READ = 0x800f9e38             # (fileInfo*, addr, offset, length, callback, priority)
CHECK_DVD_STATUS = 0x80054380       # CheckDVDDriveStatus
MUTE_AUDIO = 0x80096A20             # MuteAudioDuringDiscRead
POLL_CONTROLLER = 0x80005BA4        # PollControllerState
DC_INVALIDATE = 0x800F30CC          # DCInvalidateRange(addr, size)
DVD_CLOSE = 0x800F9B90              # DVDClose(fileInfo*)
DECODE_RESOURCE_POOL = 0x80056908   # DecodeResourcePoolCategory
# REVISION 36: the native counterpart to DECODE_RESOURCE_POOL's own
# internal allocation. DecodeResourcePoolCategory ends with:
#     if (*(ushort *)((int)resourceHandle + 10) != 0) {
#       categoryValue = MemAlloc((uint)*(ushort *)(resourceHandle+10) << 2);
#       resourceHandle[6] = categoryValue;      // == byte offset 0x18
#       ... fills it with fixed-up sub-model pointers ...
#     }
# and FreeLevelDataBuffer is the matching free:
#     if (*(int *)(dataBlock + 0x18) != 0) MemFree(*(int *)(dataBlock + 0x18));
#     *(undefined4 *)(dataBlock + 0x18) = 0;
# Native always pairs the two (FreeCardResourceSlot does exactly this for
# its own slots). This mechanic called the decode half once per record
# but never the free half, leaking one array per swapped monster per
# level visit - confirmed empirically by elimination: disabling sound
# changed nothing, disabling the CTM block changed nothing, and
# disabling the model-data block (which contains the
# DecodeResourcePoolCategory call) took the leak to exactly zero.
# The leaked size is (subCount << 2), read from the DONOR's own data,
# which is why the measured per-record size varied by monster (~176-192
# bytes = 44-48 entries) rather than being a fixed struct size.
# Safe to call unconditionally: it null-checks 0x18 before freeing and
# zeroes the field afterwards, so it is idempotent - if native also
# frees this same slot (our SLOT_BASE_ADDR region overlaps the array
# FreeCardResourceSlot indexes), the second call is a no-op rather than
# a double free.
FREE_LEVEL_DATA_BUFFER = 0x800567C8  # FreeLevelDataBuffer(dataBlock)
GET_OWNED_CARD_RECORD = 0x80065678  # GetOwnedCardRecord(playerIndex, cardId)
MEM_ALLOC = 0x800060A0               # MemAlloc(size) - single-param wrapper, confirmed via prior disassembly
MEM_FREE = 0x800f2c9c                # the REAL underlying free implementation (called "FUN_800f2c9c" in decompiled
                                      # source) - takes TWO params: (memoryArenaHandle, ptr), not a single-param
                                      # wrapper like MemAlloc above. Confirmed via the decompiled source itself:
                                      # multiple independent wrapper functions (MemFree, ReserveMemoryArenaBlock)
                                      # both call this exact same target with the same (memoryArenaHandle, ptr)

# REVISION 26: the level's own already-loaded "big blob" runtime base
# pointer (DAT_802e93a8 in the decompiled source - Ghidra's own naming
# convention encodes the address directly). FixupLevelSceneData/
# LoadLevelSceneDataTables both read *(int*)(DAT_802e93a8 + N) to find
# each data section's own offset within this SAME blob (+0x14 is our
# own native monster array's own offset - matches SLOT_BASE_ADDR's own
# source data exactly) - meaning by the time our own hooks run, this
# blob is fully loaded and its own runtime address is safely readable.
LEVEL_DATA_BASE_ADDR = 0x802E93A8
                                      # shape, and Ghidra's own "FUN_<address>" naming convention derives directly
                                      # from the function's real address. Every call site below must load
                                      # MEMORY_ARENA_HANDLE_ADDR's own current value into r3 and the pointer to
                                      # free into r4 before calling this - see emit_mem_free() below.
MEMORY_ARENA_HANDLE_ADDR = 0x802E9170  # memoryArenaHandle - confirmed via direct lookup in the decompiled project's own symbol table
QUEUE_ASYNC_FILE_LOAD = 0x80044C34  # QueueAsyncFileLoad(loadType, fileHandle, extraParam, callback)
LOAD_ENTITY_ANIMATION_TABLE = 0x8009C8F4  # LoadEntityAnimationTable(tableDescriptor)

SOUND_SLOT_FLAG_BASE = 0x80275cdc   # DAT_80275cdc - per-slot sound-active state byte (0/1/2), stride 0x18

# DAT_80275cc8 - the SAME 0x18-byte-stride struct as SOUND_SLOT_FLAG_BASE
# above, just its own buffer-pointer field (offset 0) rather than the
# active-flag field (offset 0x14, i.e. SOUND_SLOT_FLAG_BASE - 0x14 ==
# this). Confirmed via main_dol.c's own native level-exit sound cleanup:
# for each slot with flag==2, it calls MEM_FREE(memoryArenaHandle,
# (&DAT_80275cc8)[loopIndex*6]) BEFORE clearing the flag. IMPORTANT
# CORRECTION (confirmed much later in this same investigation): case
# 0x16 (the .pps file) writes ITS OWN buffer pointer here - case 0x13
# (the .sam file, the actual audio sample data) writes to a DIFFERENT
# offset within this same struct instead (REAL_SAM_BUFFER_BASE,
# below). This means the native cleanup loop's own MEM_FREE call
# above DOES correctly free the .pps buffer - but never touches the
# .sam buffer at all. See REAL_SAM_BUFFER_BASE's own comment for the
# actual fix.
SOUND_SLOT_BUFFER_BASE = SOUND_SLOT_FLAG_BASE - 0x14

# DAT_80275cd4 - the SAME 0x18-byte-stride struct again, offset 0xc
# (i.e. SOUND_SLOT_BUFFER_BASE + 0xc). This is where case 0x13's own
# "start load" handling within ProcessAsyncLoadQueue actually writes
# its own loaded buffer pointer - the REAL .sam audio sample data,
# confirmed by directly reading that case's own code in main_dol.c.
# Neither the native ResetAudioForLevelChange cleanup loop (which only
# ever touches SOUND_SLOT_BUFFER_BASE, the .pps file's own buffer) nor
# any earlier version of this file's own cleanup logic ever freed this
# specific location - every re-load for the same donor_sound_id just
# silently overwrites the pointer here, orphaning the previous
# allocation. Confirmed live as a genuine, progressive memory leak: a
# fresh save going directly from level 12 to level 18 loaded without
# issue, while the same transition after playing through several
# earlier levels first (each one re-queueing loads for whichever
# donors happen to repeat) crashed with a severe CPU exception -
# consistent with a heap eventually exhausted/corrupted by this many
# accumulated, never-freed allocations.
#
# FIXED via one-visit-deferred freeing - see PENDING_SAM_FREE_SCRATCH_
# ADDR's own docstring, near the other per-record scratch array
# allocations below, for the full mechanism and the two, different,
# more "precise" earlier attempts (immediate free; calling native
# ResetAudioForLevelChange directly) that were tried and reverted
# first, both for corrupting native OS/audio state in different ways.
# NOT YET LIVE-VERIFIED as of this fix's own introduction - the
# reasoning (one full level visit is certainly long enough for any
# sound effect to finish) is sound, but hasn't been confirmed against
# an actual crash-reproduction the way the earlier attempts were
# confirmed to fail.
REAL_SAM_BUFFER_BASE = SOUND_SLOT_BUFFER_BASE + 0xc

# ResetAudioForLevelChange (0x80094A84) - the game's own native
# audio-reset routine, and the ONLY caller of this same
# SOUND_SLOT_FLAG_BASE/SOUND_SLOT_BUFFER_BASE cleanup loop. Runs
# automatically as part of every level's own exit sequence. Several
# earlier attempts at calling this ourselves (from EXIT_HOOK, then
# HOOK2) were all reverted after causing crashes of their own - no
# longer called or referenced anywhere in this file.
DVDFILEINFO_SIZE_OFFSET = 0x34      # confirmed via case 4's own code (DAT_801b3934 = &DAT_801b3900+0x34)

COMPLETION_FLAG_ADDR = 0x802e9308   # DAT_802e9308 - set nonzero by our own callback on completion
FILEINFO_SIZE = 64                  # real GC SDK DVDFileInfo struct is 62 bytes


def _lis(rD, imm16):
    return 0x3C000000 | (rD << 21) | (imm16 & 0xFFFF)


def _ori(rA, rS, imm16):
    return 0x60000000 | (rS << 21) | (rA << 16) | (imm16 & 0xFFFF)


def _lwz(rD, offset, rA):
    return 0x80000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _lbz(rD, offset, rA):
    return 0x88000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _stw(rS, offset, rA):
    return 0x90000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stb(rS, offset, rA):
    return 0x98000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _sth(rS, offset, rA):
    return 0xB0000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _stwu(rS, offset, rA):
    return 0x94000000 | (rS << 21) | (rA << 16) | (offset & 0xFFFF)


def _addi(rD, rA, simm):
    return 0x38000000 | (rD << 21) | (rA << 16) | (simm & 0xFFFF)


def _add(rD, rA, rB):
    return 0x7C000214 | (rD << 21) | (rA << 16) | (rB << 11)


def _rlwinm(rA, rS, SH, MB, ME):
    return 0x54000000 | (rS << 21) | (rA << 16) | (SH << 11) | (MB << 6) | (ME << 1)


def _mr(rD, rS):
    return 0x7C000378 | (rS << 21) | (rD << 16) | (rS << 11)


def _li(rD, simm):
    return _addi(rD, 0, simm)


def _mflr(rD):
    return 0x7C0802A6 | (rD << 21)


def _mtlr(rS):
    return 0x7C0803A6 | (rS << 21)


def _cmpwi(rA, simm):
    return 0x2C000000 | (rA << 16) | (simm & 0xFFFF)


def _cmplwi(rA, uimm):
    return 0x28000000 | (rA << 16) | (uimm & 0xFFFF)


def _beq(from_addr, to_addr):
    return 0x41820000 | ((to_addr - from_addr) & 0xFFFC)


def _bne(from_addr, to_addr):
    return 0x40820000 | ((to_addr - from_addr) & 0xFFFC)


def _bgt(from_addr, to_addr):
    return 0x41810000 | ((to_addr - from_addr) & 0xFFFC)


def _b(from_addr, to_addr):
    return 0x48000000 | ((to_addr - from_addr) & 0x3FFFFFC)


# --- new encoders, added for the REVISION 14 data-driven loop rewrite
# (see its own docstring note above) - all standard, well-established
# PowerPC/Gekko encodings. ---

def _mtctr(rS):
    return 0x7C0903A6 | (rS << 21)


def _bdnz(from_addr, to_addr):
    # decrement CTR, branch if CTR != 0 (BO=16, BI=0)
    return 0x42000000 | ((to_addr - from_addr) & 0xFFFC)


def _divwu(rD, rA, rB):
    return 0x7C000396 | (rD << 21) | (rA << 16) | (rB << 11)


def _mullw(rD, rA, rB):
    return 0x7C0001D6 | (rD << 21) | (rA << 16) | (rB << 11)


def _subf(rD, rA, rB):
    # rD = rB - rA (note operand order)
    return 0x7C000050 | (rD << 21) | (rA << 16) | (rB << 11)


def _cmplw(rA, rB):
    return 0x7C000040 | (rA << 16) | (rB << 11)


def _lhz(rD, offset, rA):
    return 0xA0000000 | (rD << 21) | (rA << 16) | (offset & 0xFFFF)


def _bge(from_addr, to_addr):
    # branch if NOT LT (BO=4, BI=0) - used after cmplw for unsigned
    # pointer/address comparisons (addresses in the 0x80xxxxxx range
    # would be negative under a SIGNED comparison, since bit 31 is
    # set - cmplw/bge together are the unsigned-safe pairing).
    return 0x40800000 | ((to_addr - from_addr) & 0xFFFC)


def _blt(from_addr, to_addr):
    # branch if LT (BO=12, BI=0) - the complementary case to _bge above.
    return 0x41800000 | ((to_addr - from_addr) & 0xFFFC)


def hi(addr):
    return (addr >> 16) & 0xFFFF


def lo(addr):
    return addr & 0xFFFF



def get_donor_mapping(seed):
    """The single source of truth for random donor assignment - returns
    a {native_card_id: donor_card_id} dict, including Gargoyle/Horus's
    own self-mapping (see EXCLUDED_NATIVE_CARD_IDS's own comment on
    apply(), below, for why they're self-mapped rather than omitted).

    apply() itself calls this rather than duplicating this logic inline
    - added specifically because an external caller (the AP client's
    own enemy-death-detection code, which needs to know the SAME
    mapping the actual ISO patch used, to correctly match randomized
    donor species against live game state) previously reimplemented
    this logic separately by hand, and drifted out of sync with it
    (missed the EXCLUDED_NATIVE_CARD_IDS filtering on both the donor
    pool AND the native list before the shuffle, which - since the
    shuffle's own result depends on its exact input list - silently
    produced a DIFFERENT mapping than the ISO's own, despite using the
    identical seed). A single, shared function makes that class of
    drift structurally impossible instead of relying on two, separately
    maintained copies staying in sync by hand.
    """
    random.seed(seed)

    donor_pool_card_ids = sorted(
        cid for cid, m in db.MONSTERS.items()
        if m["native_levels"] and m["sound_id"] is not None
        and cid not in EXCLUDED_NATIVE_CARD_IDS
    )
    distinct_native_card_ids = sorted(set(swap["native_card_id"] for swap in SWAPS))

    # EXCLUDED_NATIVE_CARD_IDS (Gargoyle/Horus, temporary - see its own
    # comment above) are hard-mapped to THEMSELVES as their own donor,
    # rather than skipped out of SWAPS entirely - they still go through
    # the exact same donor-loading pipeline (HOOK1/HOOK2, native-
    # memory-reuse, run pooling) as every other swap, just with
    # donor_card_id == native_card_id, a no-op in terms of which
    # monster actually appears. This is deliberately NOT the same as
    # skipping their own swap: an earlier version of this fix did skip
    # them, which left their own space still counted as part of a
    # shared run's own total poolable capacity (confirmed: s13.pds's
    # own 5 native monsters - Running Bird, Gargoyle, Horus, Gorgon,
    # Black Dragon - form ONE single contiguous run) while their own
    # data never actually got refreshed, so a neighbor's donor write
    # could land directly on top of their own still-vanilla bytes.
    # Self-mapping instead means their own donor's file_offset/size is
    # IDENTICAL to their own native slot's, by construction - no
    # capacity mismatch is even possible, regardless of what else
    # shares their own run.
    natives_to_randomize = [cid for cid in distinct_native_card_ids if cid not in EXCLUDED_NATIVE_CARD_IDS]
    donor_mapping = build_random_donor_mapping(natives_to_randomize, donor_pool_card_ids, random)
    for cid in EXCLUDED_NATIVE_CARD_IDS:
        if cid in distinct_native_card_ids:
            donor_mapping[cid] = cid

    return donor_mapping


def get_randomized_monster_name_mapping(seed):
    """Thin wrapper around get_donor_mapping() for callers that want
    names rather than card_ids directly (e.g. the AP client, matching
    against get_enemy_species()'s own string output)."""
    donor_mapping = get_donor_mapping(seed)
    return {
        db.get_monster(native_card_id)["name"]: db.get_monster(donor_card_id)["name"]
        for native_card_id, donor_card_id in donor_mapping.items()
    }


def apply(patcher, output_data):
    # --- random donor assignment (now via the single shared function
    # above, so this and any external caller can never drift apart) ---
    donor_mapping = get_donor_mapping(output_data.get("Seed", -1) + 5)
    distinct_native_card_ids = sorted(donor_mapping.keys())

    # --- REVISION 28 (re-applying REVISION 27): build DONOR_TABLE
    # once, one entry per DISTINCT native species (== one entry per
    # distinct donor actually used, since the bijection is per-
    # species). Iterating distinct_native_card_ids (already sorted,
    # deterministic) gives each entry a stable, reproducible index. ---
    donor_table = []
    native_card_id_to_pool_index = {}
    for native_card_id in distinct_native_card_ids:
        donor_card_id = donor_mapping[native_card_id]
        donor_monster = db.get_monster(donor_card_id)
        donor_level_file = min(donor_monster["native_levels"].keys())
        donor_data = db.get_donor_data(donor_card_id, donor_level_file)

        pool_index = len(donor_table)
        native_card_id_to_pool_index[native_card_id] = pool_index
        donor_table.append({
            "donor_card_id": donor_card_id,
            "donor_level_id": _infer_level_id(donor_level_file),
            "donor_sound_id": donor_data["sound_id"],
            "donor_file_offset": donor_data["file_offset"],
            "donor_size": donor_data["size"],
        })

        native_name = db.get_monster(native_card_id)["name"]
        logger.info(
            f"[mechanic_randomize_monsters] random swap: "
            f"{native_name} ({hex(native_card_id)}) -> {donor_data['name']} "
            f"({hex(donor_card_id)}, from {donor_level_file})"
        )

    for swap in SWAPS:
        swap["target_level_id"] = _infer_level_id(swap["target_level_file"])
        swap["donor_pool_index"] = native_card_id_to_pool_index[swap["native_card_id"]]

    # ================================================================
    # REVISION 14: pack SWAPS into a compact binary record table
    # instead of generating unique code per swap - see this file's own
    # top docstring for the full rationale (~8KB total cave, shared
    # with every other mechanic, cannot fit 239 fully-unrolled blocks).
    # ================================================================
    record_bytes = b"".join(_pack_record(swap) for swap in SWAPS)
    record_count = len(SWAPS)
    records_addr = patcher.alloc_cave(len(record_bytes))
    patcher.patch_bytes(records_addr, record_bytes)
    records_end_addr = records_addr + len(record_bytes)
    logger.info(
        f"[mechanic_randomize_monsters] records_addr = {hex(records_addr)}, "
        f"{record_count} records, {len(record_bytes)} bytes total"
    )

    # --- REVISION 28: the shared donor table ---
    donor_table_bytes = b"".join(_pack_donor_table_entry(entry) for entry in donor_table)
    donor_table_addr = patcher.alloc_cave(len(donor_table_bytes))
    patcher.patch_bytes(donor_table_addr, donor_table_bytes)
    logger.info(
        f"[mechanic_randomize_monsters] donor_table_addr = {hex(donor_table_addr)}, "
        f"{len(donor_table)} entries, {len(donor_table_bytes)} bytes total"
    )

    # Max swaps native to any SINGLE level - this is how big the
    # HOOK1->HOOK2 handoff scratch array needs to be, NOT record_count
    # (only one level's own subset is ever "in flight" between HOOK1
    # computing a donor address and HOOK2 consuming it).
    groups = _group_swaps_by_target_level(SWAPS)
    max_group_size = max((len(g[1]) for g in groups), default=1)

    # --- shared allocations (one copy, reused across every record) ---
    fileinfo_addr = patcher.alloc_cave(FILEINFO_SIZE)
    for i in range(0, FILEINFO_SIZE, 4):
        patcher.patch_word(fileinfo_addr + i, 0)

    file_buffer_var_addr = patcher.alloc_cave(4)
    patcher.patch_word(file_buffer_var_addr, 0)

    ctm_buffer_var_addr = patcher.alloc_cave(4)
    patcher.patch_word(ctm_buffer_var_addr, 0)

    ctm_size_var_addr = patcher.alloc_cave(4)
    patcher.patch_word(ctm_size_var_addr, 0)

    lr_save_addr = patcher.alloc_cave(4)
    r29_save_addr = patcher.alloc_cave(4)
    r30_save_addr = patcher.alloc_cave(4)

    # --- callback_stub_addr runs as the DVD hardware's own async-read
    # completion callback (native name: CompleteAsyncFileLoad) - this
    # is genuine INTERRUPT-context code, invoked directly from within
    # the game's own DVD interrupt handler whenever a queued read
    # finishes, NOT called inline from our own stub's own execution
    # like HOOK_ADDR/HOOK2_ADDR/EXIT_HOOK_ADDR are. This means it can
    # interrupt ANY arbitrary code, at ANY point, with ANY registers
    # live - completely unlike a normal function call, where the
    # caller already expects r3-r12 to be volatile. An EARLIER version
    # of this callback clobbered r5/r6 with zero save/restore -
    # confirmed to be a genuine, severe bug: whatever code happened to
    # be running at the exact moment a DVD read completed could have
    # its own, unrelated r5/r6 silently corrupted the instant this
    # callback returns, with the resulting symptom depending entirely
    # on what that interrupted code was doing with those registers -
    # a very plausible explanation for hard-to-reproduce, seemingly
    # unrelated corruption (including audio, if audio-adjacent code
    # happened to be using r5/r6 at that moment).
    #
    # Uses the standard PowerPC prologue/epilogue technique (stwu r1,
    # -16(r1) to carve out a small, private stack frame; plain stw/lwz
    # off r1 to save/restore r5/r6 into it) rather than trying to save
    # into a fixed cave address via a computed-address register - an
    # EARLIER attempt at the latter tried using r0 to hold the
    # computed save address, then used r0 itself as the base register
    # (rA) of the store - this is WRONG on real PowerPC hardware: rA=0
    # in a D-form load/store's own base-register field is hardware-
    # special-cased to mean "no base, address is just the raw 16-bit
    # offset" - NOT "read r0's actual current value" - so that
    # attempt would have silently written to a near-null address
    # instead of the intended cave location. r1 has no such special
    # case and is guaranteed valid wherever any code in this game can
    # run (the same convention every other function's own prologue
    # already relies on), so anchoring off r1 sidesteps the problem
    # entirely rather than working around it.
    callback_instructions = [
        _stwu(1, -16, 1),   # carve out a private 16-byte frame, save old r1 at new r1[0]
        _stw(5, 4, 1),      # save r5
        _stw(6, 8, 1),      # save r6

        # original callback body
        _li(5, 1),
        _lis(6, hi(COMPLETION_FLAG_ADDR)),
        _ori(6, 6, lo(COMPLETION_FLAG_ADDR)),
        _stb(5, 0, 6),

        _lwz(5, 4, 1),      # restore r5
        _lwz(6, 8, 1),      # restore r6

        # pop the frame (restores r1) then return
        _lwz(1, 0, 1),
        0x4E800020,  # blr
    ]
    # Allocated based on the instruction list's own actual length, not a
    # hardcoded count - an earlier version hardcoded "9" while the list
    # itself had grown to 11 entries, a genuine buffer-overflow bug
    # (writing 44 bytes into a 36-byte cave reservation, silently
    # spilling into whatever got allocated next). Deriving the size
    # directly from len(callback_instructions) makes this class of
    # mismatch structurally impossible going forward.
    callback_stub_addr = patcher.alloc_cave(len(callback_instructions) * 4)
    patcher.write_code(callback_stub_addr, callback_instructions)

    # --- REVISION 17 fix: table_descriptor CANNOT be shared/transient
    # scratch like it was before. Decompiling LoadEntityAnimationTable
    # itself revealed it does its OWN internal MemAlloc (a THIRD
    # allocation, invisible to us until now) and stores that pointer
    # into tableDescriptor[2] - and every other native call site in
    # the game passes a DEDICATED, PERMANENT struct (never a shared,
    # transient one), strongly implying tableDescriptor[2] needs to
    # stay alive and findable for as long as that specific monster
    # exists in the level (presumably for later rendering to reference
    # back through it). Sharing a single table_descriptor across every
    # monster in a level meant each new monster's own call silently
    # orphaned the PREVIOUS monster's own tableDescriptor[2] - matching
    # the "bugged textures on revisit" symptom exactly. Fixed by giving
    # each slot POSITION (0..max_group_size-1, the same idx already
    # used for donor_addr_scratch etc.) its own dedicated 3-word
    # descriptor, and tracking tableDescriptor[2] itself the same way
    # ctm_buffer/file_buffer are tracked, for EXIT_HOOK to free too.
    table_descriptor_scratch_addr = patcher.alloc_cave(max_group_size * 3 * 4)
    for i in range(max_group_size):
        patcher.patch_word(table_descriptor_scratch_addr + i * 12, 0)
        patcher.patch_word(table_descriptor_scratch_addr + i * 12 + 4, 0)
        patcher.patch_word(table_descriptor_scratch_addr + i * 12 + 8, 0)
    current_table_descriptor_addr_addr = patcher.alloc_cave(4)

    last_resolved_texture_array_scratch_addr = patcher.alloc_cave(max_group_size * 4)
    for i in range(max_group_size):
        patcher.patch_word(last_resolved_texture_array_scratch_addr + i * 4, 0)
    current_resolved_texture_array_slot_addr_addr = patcher.alloc_cave(4)

    read_offset_var_addr = patcher.alloc_cave(4)
    read_length_var_addr = patcher.alloc_cave(4)
    monster_offset_var_addr = patcher.alloc_cave(4)
    patcher.patch_word(read_offset_var_addr, 0)
    patcher.patch_word(read_length_var_addr, 0)
    patcher.patch_word(monster_offset_var_addr, 0)

    # Writable path template buffers - shared, digit positions patched
    # at runtime (via format_digits, see below) with whichever record
    # is currently being processed. Replaces the old per-swap static
    # path strings entirely.
    donor_level_path_addr = patcher.alloc_cave(14)
    patcher.patch_bytes(donor_level_path_addr, b"game/s00.pds\x00")
    DONOR_LEVEL_PATH_DIGITS_OFFSET = 6  # "s[XX].pds" - 2 digits

    ctm_path_addr = patcher.alloc_cave(19)
    patcher.patch_bytes(ctm_path_addr, b"game/ctm/e000.CTM\x00")
    CTM_PATH_DIGITS_OFFSET = 10  # "e[XXX].CTM" - 3 digits

    sound_path_addr = patcher.alloc_cave(15)
    patcher.patch_bytes(sound_path_addr, b"sound/e000.pps\x00")
    SOUND_PATH_DIGITS_OFFSET = 7  # "e[XXX].pps" - 3 digits

    sound_sam_path_addr = patcher.alloc_cave(15)
    patcher.patch_bytes(sound_sam_path_addr, b"sound/e000.sam\x00")
    SAM_PATH_DIGITS_OFFSET = 7  # "e[XXX].sam" - 3 digits

    # Outer-loop state (memory-resident, not registers - the loop makes
    # many "bl" calls to game functions that may clobber any volatile
    # register, and only r29/r30 have been empirically confirmed safe
    # across those SPECIFIC calls, both of which are already claimed
    # for other short-lived purposes within a single record's own
    # processing - see this file's own REVISION 14 docstring note).
    current_record_ptr_addr = patcher.alloc_cave(4)
    donor_scratch_idx_addr = patcher.alloc_cave(4)
    current_donor_table_entry_addr_addr = patcher.alloc_cave(4)  # REVISION 28: THIS record's own resolved DONOR_TABLE entry address, fixed at match-time

    # --- REVISION 16 fix (restored - see REVISION 25's own note in
    # this file's top docstring: the private pool from REVISIONS
    # 22-24 was reverted after it caused failures the original design
    # never had - an opening-movie allocation failure and a
    # level-completion crash, both in code paths our per-visit
    # MemAlloc/MemFree design never touched): our own MemAlloc'd
    # ctm_buffer/file_buffer are never freed by native code (confirmed
    # via the decompiled source - FreeLevelResources() frees the
    # NATIVE level's own big loaded buffers on every level entry, but
    # our own separate MemAlloc calls are invisible to that cleanup).
    # Since a monster's own donor data must stay valid for the WHOLE
    # time the player is in a level, we can't free it right after use
    # either - instead, these two arrays remember what we allocated
    # last time THIS level's own Nth matching slot was used, so
    # EXIT_HOOK (the real level-exit point, found in main()'s own
    # compiled loop, not LoadLevelAndShowLoadingScreen at all) can free
    # the old buffer when actually leaving the level. Sized to
    # max_group_size (same reasoning as donor_addr_scratch above) and
    # reset to 0 at the START of every HOOK1 invocation (see below) -
    # these track only what THIS visit allocates, for EXIT_HOOK to
    # free at the real end of that same visit. (Confirmed via direct
    # testing that freeing ctm_buffer any EARLIER than this - even
    # right after its own synchronous use inside
    # LoadEntityAnimationTable - breaks every texture: materialData,
    # the pointer into our own ctm_buffer, gets read again later,
    # likely by a lazy/deferred GX texture upload, not just during
    # that initial decode.)
    # REVISION 37 (cave-space pass): target_slot_addr was being
    # recomputed from scratch at FIVE separate points inside a single
    # record's own body, 9 instructions each (read record ptr, load
    # table_index, multiply by stride, add base). It is identical at
    # every one of those points, so compute it once and reload it in 3.
    # A register would be cheaper still, but HOOK2 preserves no
    # callee-saved registers (it saves LR to a static word rather than
    # carving a frame), so anything held across its bl calls has to
    # live in memory.
    current_target_slot_addr_addr = patcher.alloc_cave(4)
    current_ctm_buffer_slot_addr_addr = patcher.alloc_cave(4)
    current_file_buffer_slot_addr_addr = patcher.alloc_cave(4)
    last_ctm_buffer_scratch_addr = patcher.alloc_cave(max_group_size * 4)
    last_file_buffer_scratch_addr = patcher.alloc_cave(max_group_size * 4)
    # REVISION 37 (cave-space pass): the REVISION 36/36b machinery
    # that used to live here - a last_target_slot_scratch_addr array,
    # its zeroing pass, a per-record store in HOOK2, and a matching
    # FreeLevelDataBuffer call in EXIT_HOOK - has been REMOVED as
    # redundant. It existed to free the array OUR own
    # DecodeResourcePoolCategory call allocates into the slot
    # ("B"), but the native exit-time cleanup already reclaims that
    # slot: before any fix, the measured leak was exactly ONE block
    # per record, not two, and the block that leaked was the NATIVE
    # array ("A") our re-decode orphaned - which means B was always
    # being freed by native. REVISION 36c's pre-free (immediately
    # before the decode call in HOOK2) is what actually fixes the
    # leak, and it is sufficient on its own.
    for i in range(max_group_size):
        patcher.patch_word(last_ctm_buffer_scratch_addr + i * 4, 0)
        patcher.patch_word(last_file_buffer_scratch_addr + i * 4, 0)

    # --- REVISION 34: the .sam "leak" does not exist, and the
    # one-visit-deferred free that used to live here has been REMOVED
    # (along with its PENDING_SAM_FREE_SCRATCH_ADDR array, its
    # free-loop at the top of hook2, and its stash step down in the
    # sound-loading section).
    #
    # Confirmed directly in the decompiled source: ProcessAsyncLoadQueue
    # has TWO switches on the load type - one that STARTS the load and
    # one that runs on COMPLETION. For type 0x13 (the .sam load, which
    # is exactly the type this mechanic queues too), the completion
    # handler runs, unconditionally:
    #
    #     case 0x13:
    #       LoadShopUIElement(sound_id, sound_id);   // fixes up the
    #                                                // slot's other
    #                                                // pointer fields,
    #                                                // then hands them
    #                                                // to FUN_80139600
    #       FreeShopUIElement(sound_id);             // MemFree(
    #                                                // REAL_SAM_BUFFER_
    #                                                // BASE[sound_id])
    #
    # i.e. the native game ALREADY frees the .sam buffer itself, the
    # moment the load completes - almost certainly because FUN_80139600
    # has by then uploaded the raw samples to ARAM (audio RAM), making
    # the main-RAM staging copy dead weight. The smaller .pps sequence
    # data (offset +0 in the same slot struct) is CPU-read and stays
    # resident, which is why only IT is freed later, in
    # ResetAudioForLevelChange.
    #
    # Crucially, FreeShopUIElement does NOT null the field afterwards,
    # so REAL_SAM_BUFFER_BASE[sound_id] is left holding a DANGLING
    # pointer to already-freed memory. Every "leak fix" attempt in this
    # file's own history was therefore reading a stale pointer and
    # handing it to MemFree a second time - a straight double free.
    #
    # This was confirmed live, and explains every symptom seen while
    # chasing it: the pointer always looked perfectly valid (it WAS a
    # real allocation, just already freed); the crash was always inside
    # MEM_FREE's own free-list insert/coalesce walk; the "allocator
    # header" at ptr-0x1c/ptr-0x20 contained float-shaped audio/texture
    # bytes (the freed block had since been recycled and written over by
    # some later allocation); it took 2+ visits to the SAME level before
    # leaving to reproduce (the block has to actually get reused in
    # between); and NOPing the free-loop made it disappear entirely.
    #
    # DO NOT re-add any .sam freeing here. Nothing this mechanic
    # allocates for sound needs freeing - the native completion handler
    # covers our type-0x13 loads exactly as it covers its own. ---
    # --- REVISION 26: the global run table (one shared copy, indexed
    # by each record's own native_run_id) plus a matching per-run
    # runtime cursor array. Each run entry is (start_offset,
    # total_size) within the level's own already-loaded blob (see
    # _find_contiguous_native_runs()/LEVEL_DATA_BASE_ADDR's own notes)
    # - both fixed at patch-generation time, since they only depend on
    # the LEVEL FILE's own layout, not on which donor gets randomly
    # assigned. The cursor array is the only genuinely per-visit,
    # runtime-mutable piece - reset to 0 for every run at the start of
    # every HOOK1 invocation (see below), since a fresh level visit
    # means the whole run is available again regardless of what a
    # PREVIOUS, different level's own visit consumed.
    #
    # REVISION 32: both fields shrunk from u32 to u24 (max real value
    # for either is a few MB, well under the 16MB u24 ceiling) - read
    # at runtime via the same "load a word 1 byte early, mask off the
    # top byte" trick as DONOR_TABLE. Unlike DONOR_TABLE, start_offset
    # IS the very first field of the very first entry, with nothing
    # before it to safely borrow from - one padding byte at the very
    # start of the whole table fixes this for every entry uniformly
    # (each entry's own start_offset then borrows the previous byte,
    # whether that's the padding byte for entry 0, or the previous
    # entry's own last byte for everyone else).
    run_table_bytes = b"\x00"  # 1-byte padding - see note above
    for start_offset, total_size in RUN_TABLE:
        run_table_bytes += _pack_u24(start_offset) + _pack_u24(total_size)
    run_table_addr = patcher.alloc_cave(len(run_table_bytes))
    patcher.patch_bytes(run_table_addr, run_table_bytes)
    RUN_TABLE_ENTRY_SIZE = 6
    run_cursor_scratch_addr = patcher.alloc_cave(len(RUN_TABLE) * 4)
    for i in range(len(RUN_TABLE)):
        patcher.patch_word(run_cursor_scratch_addr + i * 4, 0)

    # EXIT_HOOK's own loop counter (separate from donor_scratch_idx,
    # which belongs to HOOK1/HOOK2 and runs at a different time)
    exit_scratch_idx_addr = patcher.alloc_cave(4)

    logger.info(f"[mechanic_randomize_monsters] max_group_size = {max_group_size}")
    logger.info(f"[mechanic_randomize_monsters] max_group_size = {max_group_size}")
    logger.info(f"[mechanic_randomize_monsters] RUN_TABLE has {len(RUN_TABLE)} runs, {len(RUN_TABLE)*8} bytes")

    def emit_load_field(reg, field_offset, size):
        """Reloads current_record_ptr (from memory) into `reg`, then
        loads the field at field_offset (u8/u16/u32 per size) into
        that SAME register (the pointer itself isn't needed after)."""
        instrs = [
            _lis(reg, hi(current_record_ptr_addr)),
            _ori(reg, reg, lo(current_record_ptr_addr)),
            _lwz(reg, 0, reg),
        ]
        if size == 1:
            instrs.append(_lbz(reg, field_offset, reg))
        elif size == 2:
            instrs.append(_lhz(reg, field_offset, reg))
        elif size == 4:
            instrs.append(_lwz(reg, field_offset, reg))
        else:
            raise ValueError(f"unsupported field size {size}")
        return instrs

    def emit_load_target_slot_addr(reg):
        """REVISION 31: computes target_slot_addr = SLOT_BASE_ADDR +
        table_index*SLOT_STRIDE into `reg`, reading table_index (u8)
        from the current record - replaces the old direct u32 field
        load, since every swap's own target_slot_addr is derivable
        this way (confirmed: table_index always fits a u8). Uses r0 as
        a general-purpose scratch for the multiplicand/base (safe -
        r0's own special "treated as 0" behavior only applies when
        used as a base register in d(rA) addressing, not as a plain
        arithmetic operand here)."""
        return [
            _lis(reg, hi(current_record_ptr_addr)),
            _ori(reg, reg, lo(current_record_ptr_addr)),
            _lwz(reg, 0, reg),
            _lbz(reg, REC_TABLE_INDEX, reg),  # reg = table_index
            _li(0, SLOT_STRIDE),
            _mullw(reg, reg, 0),              # reg = table_index * SLOT_STRIDE
            _lis(0, hi(SLOT_BASE_ADDR)),
            _ori(0, 0, lo(SLOT_BASE_ADDR)),
            _add(reg, reg, 0),                # reg = SLOT_BASE_ADDR + table_index*SLOT_STRIDE
        ]

    def emit_load_donor_field(reg, field_offset, size):
        """REVISION 28: same pattern as emit_load_field above, but reads
        from current_donor_table_entry_addr_addr instead of the record
        itself - this record's own donor_pool_index has already been
        resolved into a DONOR_TABLE entry address once, cached there
        right after the record was confirmed to match (see the "claim
        scratch slot" step in both HOOK1 and HOOK2).
        REVISION 32: size==3 reads a u24 field - loads a full word
        starting ONE BYTE EARLY (safe here since DONOR_TABLE's own
        u24 fields are never first in the struct - there's always a
        preceding field's own last byte to harmlessly "borrow"), then
        masks off the resulting top byte (rlwinm keeping bits 8-31)."""
        instrs = [
            _lis(reg, hi(current_donor_table_entry_addr_addr)),
            _ori(reg, reg, lo(current_donor_table_entry_addr_addr)),
            _lwz(reg, 0, reg),
        ]
        if size == 1:
            instrs.append(_lbz(reg, field_offset, reg))
        elif size == 2:
            instrs.append(_lhz(reg, field_offset, reg))
        elif size == 3:
            instrs.append(_lwz(reg, field_offset - 1, reg))
            instrs.append(_rlwinm(reg, reg, 0, 8, 31))
        elif size == 4:
            instrs.append(_lwz(reg, field_offset, reg))
        else:
            raise ValueError(f"unsupported field size {size}")
        return instrs

    def emit_load_addr(reg, addr):
        return [_lis(reg, hi(addr)), _ori(reg, reg, lo(addr))]

    def emit_load_mem_word(reg, addr):
        return [_lis(reg, hi(addr)), _ori(reg, reg, lo(addr)), _lwz(reg, 0, reg)]

    def emit_store_mem_word(value_reg, addr_scratch_reg, addr):
        return [
            _lis(addr_scratch_reg, hi(addr)),
            _ori(addr_scratch_reg, addr_scratch_reg, lo(addr)),
            _stw(value_reg, 0, addr_scratch_reg),
        ]

    def emit_mem_free(fills, instructions, ptr_reg):
        """Calls MEM_FREE (the real underlying free implementation, NOT
        a single-param wrapper) with the correct two-parameter calling
        convention: r4 = the pointer to free (moved from ptr_reg first,
        since r3 is about to be overwritten), r3 = memoryArenaHandle's
        own CURRENT value (loaded fresh - it's a real game global, not
        a fixed constant, so it must be read at call time, not baked
        in). Takes the register explicitly since call sites vary (all
        three current EXIT_HOOK call sites pass 5, having just loaded
        the pointer to free into r5 via an lwz) rather than assuming
        any one fixed register silently."""
        instructions.append(_mr(4, ptr_reg))
        instructions += emit_load_mem_word(3, MEMORY_ARENA_HANDLE_ADDR)
        idx = len(instructions)
        instructions.append(None)
        fills.append((idx, "bl", MEM_FREE))

    # ================================================================
    # format_digits subroutine: r3=value, r4=buffer addr of the FIRST
    # (leftmost) digit position, r5=digit_count (2 or 3). Writes
    # digit_count ASCII decimal digits (zero-padded) into the buffer,
    # most significant digit first. Self-contained (no "bl" calls made
    # from inside it), so it's safe to use CTR/bdnz for its own tiny
    # loop even though CTR isn't safe to rely on across calls to game
    # functions elsewhere in this file.
    # ================================================================
    fd_instructions = [
        _mtctr(5),
        _add(6, 4, 5),   # r6 = one-past-the-last digit position
    ]
    fd_loop_label = len(fd_instructions)
    fd_instructions += [
        _addi(6, 6, -1),
        _li(7, 10),
        _divwu(8, 3, 7),      # r8 = value / 10
        _mullw(9, 8, 7),      # r9 = (value/10)*10
        _subf(10, 9, 3),      # r10 = value - r9 = value % 10
        _addi(10, 10, 0x30),  # ASCII '0' + digit
        _stb(10, 0, 6),
        _mr(3, 8),            # value = value / 10 for next digit
    ]
    fd_bdnz_idx = len(fd_instructions)
    fd_instructions.append(None)
    fd_instructions.append(0x4E800020)  # blr

    format_digits_addr = patcher.alloc_cave(len(fd_instructions) * 4)
    fd_from_addr = format_digits_addr + fd_bdnz_idx * 4
    fd_to_addr = format_digits_addr + fd_loop_label * 4
    fd_instructions[fd_bdnz_idx] = _bdnz(fd_from_addr, fd_to_addr)
    patcher.write_code(format_digits_addr, fd_instructions)
    logger.info(f"[mechanic_randomize_monsters] format_digits_addr = {hex(format_digits_addr)}")

    def emit_zero_array(fills, instructions, labels, label_tag, array_addr, count):
        """Zeros `count` consecutive words starting at array_addr using
        a REAL runtime loop (mtctr/bdnz), not Python-side unrolling -
        fixed ~32 bytes of code regardless of count, versus ~12 bytes
        PER WORD if unrolled. Safe to use CTR here specifically because
        no "bl" calls happen inside this loop (unlike the main
        per-record loops, which make many calls to game functions and
        so keep all persistent state in memory instead - see this
        file's own REVISION 14 docstring note). label_tag must be
        unique per call site within the same stub."""
        instructions += emit_load_addr(3, array_addr)
        instructions.append(_li(4, 0))
        instructions.append(_li(5, count))
        instructions.append(_mtctr(5))
        labels[f"zero_loop_{label_tag}"] = len(instructions)
        instructions.append(_stw(4, 0, 3))
        instructions.append(_addi(3, 3, 4))
        idx = len(instructions)
        instructions.append(None)
        fills.append((idx, "bdnz", f"zero_loop_{label_tag}"))

    def emit_format_digits_call(fills, instructions, field_offset, field_size, buffer_addr, digit_count):
        """Loads the given record field, then calls format_digits to
        write it as digit_count zero-padded ASCII decimal digits into
        buffer_addr (its own first/leftmost digit position)."""
        instructions += emit_load_field(3, field_offset, field_size)
        instructions += emit_load_addr(4, buffer_addr)
        instructions.append(_li(5, digit_count))
        idx = len(instructions)
        instructions.append(None)
        fills.append((idx, "bl", format_digits_addr))

    def emit_format_digits_call_donor(fills, instructions, field_offset, field_size, buffer_addr, digit_count):
        """REVISION 28: same as emit_format_digits_call above, but reads
        the field from the cached DONOR_TABLE entry address instead of
        the record itself."""
        instructions += emit_load_donor_field(3, field_offset, field_size)
        instructions += emit_load_addr(4, buffer_addr)
        instructions.append(_li(5, digit_count))
        idx = len(instructions)
        instructions.append(None)
        fills.append((idx, "bl", format_digits_addr))

    # ================================================================
    # HOOK2 stub: same flat loop structure as HOOK1, over the same
    # record table - for each record whose target_level_id matches,
    # read back the donor address HOOK1 computed and stashed into
    # donor_addr_scratch[donor_scratch_idx] (HOOK2 re-derives the same
    # idx sequence independently by re-running the identical
    # level-filter scan in the same order - deterministic, so it lines
    # up with HOOK1's own writes without needing to pass anything
    # except the scratch array itself between the two hooks), write
    # word[0] to the target slot, call DecodeResourcePoolCategory,
    # apply the word[8] card-ID-derived fix via GetOwnedCardRecord.
    # ================================================================
    instructions2 = [
        _mflr(0),
        _lis(3, hi(lr_save_addr)),
        _ori(3, 3, lo(lr_save_addr)),
        _stw(0, 0, 3),
        _lis(3, hi(r29_save_addr)),
        _ori(3, 3, lo(r29_save_addr)),
        _stw(29, 0, 3),
        _lis(3, hi(r30_save_addr)),
        _ori(3, 3, lo(r30_save_addr)),
        _stw(30, 0, 3),
    ]

    fills2 = []
    labels2 = {}

    # REVERTED (third attempt at calling ResetAudioForLevelChange
    # ourselves, third failure) - this specific call, from right here
    # at the start of HOOK2, before queuing this visit's own new sound
    # loads, was reasoned to be safe from the same race the first two
    # attempts hit (nothing of OUR own should still be in flight by
    # this point). Confirmed wrong in a new way: crashed on level 1's
    # own FIRST-EVER load in a session - the one case where the timing
    # reasoning doesn't hold, since native game startup itself may
    # still have its own sound-category preloading in flight around
    # this exact point (StopAllSoundCategories/PreloadAllSoundCategor
    # ies - the ONLY other native callers of this same SOUND_SLOT_FLAG
    # _BASE mechanism - confirmed earlier to run as generic, session/
    # level-startup-tied logic, not specifically gated on "previous
    # visit already finished"). Three separate call sites (EXIT_HOOK,
    # then EXIT_HOOK again with the real function, now HOOK2) have all
    # hit some version of this same race - treating this function as
    # unsafe to call ourselves from ANY point in our own hooks until a
    # genuinely different approach is found, not just a different
    # timing within the same approach.

    # REVISION 32: HOOK1 removed entirely - once sound, file_buffer/
    # model data, and CTM/texture loading all moved here, HOOK1's own
    # loop had nothing left to do (every value it computed was already
    # independently, redundantly recomputed here too). See this file's
    # own REVISION 32 note near HOOK_ADDR's own (former) definition for
    # the fuller rationale.

    instructions2 += emit_load_addr(3, records_addr)
    instructions2 += emit_store_mem_word(3, 4, current_record_ptr_addr)
    instructions2.append(_li(3, 0))
    instructions2 += emit_store_mem_word(3, 4, donor_scratch_idx_addr)

    # --- MOVED FROM HOOK1 (REVISION 32): zero this visit's own buffer-
    # tracking arrays fresh, every time this hook runs - they must not
    # carry over stale pointers from a previous, unrelated level's own
    # visit; EXIT_HOOK relies on these correctly reflecting only what
    # THIS visit allocated. This used to run at HOOK1's own start,
    # before HOOK1 itself became entirely redundant and was removed -
    # moved here rather than dropped, since the correctness requirement
    # itself didn't go away just because HOOK1 did. ---
    emit_zero_array(fills2, instructions2, labels2, "ctm", last_ctm_buffer_scratch_addr, max_group_size)
    emit_zero_array(fills2, instructions2, labels2, "file", last_file_buffer_scratch_addr, max_group_size)
    emit_zero_array(fills2, instructions2, labels2, "texarr", last_resolved_texture_array_scratch_addr, max_group_size)
    emit_zero_array(fills2, instructions2, labels2, "runcursor", run_cursor_scratch_addr, len(RUN_TABLE))
    emit_zero_array(fills2, instructions2, labels2, "tabledesc", table_descriptor_scratch_addr, max_group_size * 3)

    # REVISION 34: the ".sam buffer leak fix, part 1 of 2" free-loop
    # that used to sit here has been REMOVED - the native type-0x13
    # completion handler already frees every .sam buffer itself, so this
    # loop was double-freeing already-freed memory. See the REVISION 34
    # note further up (where PENDING_SAM_FREE_SCRATCH_ADDR used to be
    # allocated) for the full evidence.

    labels2["loop_top"] = len(instructions2)
    instructions2 += emit_load_mem_word(3, current_record_ptr_addr)
    instructions2 += emit_load_addr(4, records_end_addr)
    instructions2.append(_cmplw(3, 4))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bge", "loop_done"))

    instructions2 += emit_load_field(5, REC_TARGET_LEVEL_ID, 1)
    instructions2 += emit_load_addr(6, LEVEL_ID_ADDR)
    instructions2.append(_lbz(6, 0, 6))
    instructions2.append(_cmplw(5, 6))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bne", "next_record"))

    # --- REVISION 28: resolve this record's own donor_pool_index into
    # a real DONOR_TABLE entry address once, right here (this used to
    # mirror an identical step HOOK1 also performed, before HOOK1 was
    # removed entirely - REVISION 32). ---
    instructions2 += emit_load_field(7, REC_DONOR_POOL_INDEX, 1)
    instructions2 += [_li(8, DONOR_TABLE_ENTRY_SIZE), _mullw(7, 7, 8)]
    instructions2 += emit_load_addr(8, donor_table_addr)
    instructions2 += [_add(7, 7, 8)]
    instructions2 += emit_store_mem_word(7, 8, current_donor_table_entry_addr_addr)

    # REVERTED (per explicit request): removed the entire flag=3
    # marking/cleanup system (both this HOOK2-side half and the
    # EXIT_HOOK-side half) - reverting all the way back to the state
    # right after sound loading was first moved to HOOK2, before any
    # of this cleanup logic was ever added. Relies entirely on the
    # native ResetAudioForLevelChange again for sound-slot cleanup.

    # === SOUND: moved here from HOOK1 - HOOK1 fires immediately after
    # the current level's own file load gets QUEUED (right after
    # LoadLevelAndShowLoadingScreen's own "QueueAsyncFileLoad(3, ...)"
    # call), well BEFORE the native while loop that actually drains
    # that queue (including FixupLevelSceneData, the level file's own
    # completion handler) has even started - see HOOK_ADDR's own
    # top-of-file comment. That means any donor sound whose own
    # resolved level happens to match the level currently loading
    # would have HOOK1 re-open and re-read that SAME file via
    # DVDFastOpen while the native game's own load of it might still
    # be genuinely in progress - confirmed as the direct explanation
    # for an intermittent, RNG-dependent crash (only ever hit when a
    # donor's own unique native level matched the level being loaded).
    # HOOK2, by contrast, is documented as firing only once ALL native
    # level-loading is guaranteed complete - moving sound loading here
    # eliminates the hazard entirely, since there's no longer any
    # native load of the current level's own file still in flight for
    # us to race against, regardless of which donor gets used. Uses
    # the same cave-allocated sound_path_addr/sound_sam_path_addr
    # scratch buffers HOOK1 used to use - these aren't specific to
    # either hook, just shared scratch memory.
    emit_format_digits_call_donor(fills2, instructions2, DTE_DONOR_CARD_ID, 1, sound_path_addr + SOUND_PATH_DIGITS_OFFSET, 3)
    emit_format_digits_call_donor(fills2, instructions2, DTE_DONOR_CARD_ID, 1, sound_sam_path_addr + SAM_PATH_DIGITS_OFFSET, 3)

    # REMOVED (per explicit request): the flag=3 deferred-cleanup
    # block that used to run here. Precise interaction with several
    # pieces of native code (the audio-DSP hardware driver, whatever
    # interrupt-context code corrupted a function pointer during live
    # debugging attempts) was never fully, confidently established -
    # removed entirely rather than keep a mechanism whose own full
    # behavior alongside native code isn't precisely understood.

    # --- Guard: skip our own sound loading entirely if this donor's
    # own sound_id slot is already non-zero (flag != 0), rather than
    # unconditionally queueing our own loads on top of whatever's
    # already there. Confirmed via main_dol.c that StopAllSoundCategories/
    # PreloadAllSoundCategories/SetVolumeAllSoundCategories - all fully
    # native, running independently of and uncoordinated with anything
    # in this file - preload sound for every monster in the PLAYER's
    # OWN currently-equipped deck (via IsCardInKnownList), using this
    # exact same SOUND_SLOT_FLAG_BASE/SOUND_SLOT_BUFFER_BASE system and
    # the exact same case 0x16/case 0x13 pattern. If the player has
    # captured and deck-equipped a donor monster, that native code and
    # this one can both try to activate the SAME sound_id's slot at
    # different, uncoordinated times - confirmed live via two related
    # crashes (identical SRR0 both times, one during general combat,
    # one specifically mid-card-sound-effect-playback with reported
    # audio distortion) consistent with exactly this kind of race: two
    # independent, unsynchronized loads/frees on the same shared slot.
    # Neither this file's own code nor the native callers ever checked
    # the existing flag before writing - this guard makes OUR OWN side
    # of that race disappear entirely: if something (a previous visit
    # of ours, OR the native card-sound system) has already claimed
    # this exact sound_id, we leave it alone rather than contending
    # for it. This does NOT fix the native side ever re-queueing on
    # top of OUR OWN already-active slot - only removes our own
    # contribution to the collision, since patching the several native
    # callers directly would be considerably more invasive.
    #
    # RE-ENABLED (per explicit request) after a temporary, diagnostic
    # disable - that test (guard removed, sound re-enabled) produced
    # NO crash across repeated level-1 re-entries, where the guard's
    # own presence had previously coincided with one. Re-enabling now
    # specifically to confirm causation via direct A/B comparison,
    # rather than concluding from a single, one-directional test.
    instructions2 += emit_load_donor_field(3, DTE_DONOR_SOUND_ID, 2)
    instructions2.append(_li(4, 0x18))
    instructions2.append(_mullw(3, 3, 4))
    instructions2 += emit_load_addr(4, SOUND_SLOT_FLAG_BASE)
    instructions2.append(_add(3, 3, 4))
    instructions2.append(_lbz(3, 0, 3))
    instructions2.append(_cmpwi(3, 0))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bne", "hook2_sound_done"))

    # REVERTED (per explicit request): all the way back to the state
    # right after sound loading was first moved to HOOK2 - restored
    # the original case 0x16 (.pps) + case 0x13 (.sam) pairing. Every
    # subsequent attempt (case 0x16 for both, then a fully direct
    # load with ordering/DC_INVALIDATE/DVD_CLOSE fixes, then back to
    # case 0x16 for both again) failed to restore working sound, so
    # none of those changes were actually addressing the real cause -
    # reverting the whole chain rather than continuing to guess at
    # increasingly complex variations on it.
    instructions2 += emit_load_addr(3, sound_path_addr)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CONVERT_PATH))
    instructions2 += [_cmpwi(3, -1)]
    idx2 = len(instructions2)
    instructions2.append(None)
    # REVISION 35 (leak/bad-free audit): on .pps failure this used to
    # branch to its own "hook2_skip_sound_16" label, which fell straight
    # through into the .sam load below and, if THAT succeeded, still set
    # SOUND_SLOT_FLAG_BASE[sound_id] = 2. That flag is what tells the
    # native ResetAudioForLevelChange cleanup loop to
    # MemFree(SOUND_SLOT_BUFFER_BASE[sound_id]) (offset +0, the .pps
    # buffer) at level exit - so setting it without a .pps load having
    # actually been queued handed MemFree whatever stale value that
    # field already held (a pointer a PREVIOUS visit's own
    # ResetAudioForLevelChange had already freed, or uninitialized
    # garbage). Same failure class as the .sam double free removed in
    # REVISION 34. Skip the entire sound setup for this record instead:
    # no .pps means no .sam worth loading and, critically, no flag.
    fills2.append((idx2, "beq", "hook2_sound_done"))
    instructions2.append(_mr(4, 3))
    instructions2.append(_li(3, 0x16))
    instructions2 += emit_load_donor_field(5, DTE_DONOR_SOUND_ID, 2)
    instructions2.append(_li(6, 0))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", QUEUE_ASYNC_FILE_LOAD))

    # --- sound-slot-active flag: SOUND_SLOT_FLAG_BASE + sound_id*0x18 ---
    # REVISION 35: moved UP to here, immediately after the .pps load is
    # queued, from its old position after the .sam load below. The flag
    # means exactly "this slot's own .pps buffer is live and needs
    # freeing at level exit", so it must be tied to the .pps queue
    # succeeding and nothing else. Previously it sat after the .sam
    # load, so a .sam path-resolution failure (which branches to
    # hook2_sound_done) skipped the flag write even though the .pps
    # load HAD already been queued - leaving flag 0 on a slot whose
    # .pps buffer was genuinely allocated, so the native cleanup loop
    # skipped it and the buffer leaked. Setting it here fixes that
    # direction too.
    instructions2 += emit_load_donor_field(3, DTE_DONOR_SOUND_ID, 2)
    instructions2.append(_li(4, 0x18))
    instructions2.append(_mullw(3, 3, 4))
    instructions2 += emit_load_addr(4, SOUND_SLOT_FLAG_BASE)
    instructions2.append(_add(3, 3, 4))
    instructions2.append(_li(5, 2))
    instructions2.append(_stb(5, 0, 3))

    # REMOVED (superseded by a direct native-code fix instead - see
    # FUN_80130ce8's own hook installation near this mechanic's own
    # EXIT_HOOK/HOOK/HOOK2 installations, below): earlier versions of
    # this section pre-initialized SOUND_SLOT_DERIVED_PTR_BASE/_2/_3
    # and SOUND_SLOT_BUFFER_BASE with various dummy values, on the
    # theory that feeding LoadShopUIElement "safe" placeholder data
    # would prevent the crash it eventually leads to. Confirmed this
    # was never the right layer to fix: the actual crash is a genuine,
    # unconditional "not found" fallthrough bug in FUN_80130ce8 itself
    # (a completely separate, native lookup table, unrelated to
    # anything in our own sound-slot struct) - no combination of
    # placeholder data in OUR OWN struct could ever prevent it, since
    # that struct was never what the crashing code path actually
    # depends on. Patching FUN_80130ce8 directly, at its own root
    # cause, replaces all of this.

    # REVISION 34: the stash step (".sam buffer leak fix, part 2 of 2")
    # that used to sit here has been REMOVED, together with its
    # free-loop counterpart at the top of hook2.
    #
    # Both existed to fix a .sam buffer leak that, on direct inspection
    # of the decompiled source, DOES NOT EXIST: the native completion
    # handler for type-0x13 loads (the type this mechanic queues) calls
    # FreeShopUIElement, which MemFree's REAL_SAM_BUFFER_BASE[sound_id]
    # the moment the load finishes - without nulling the field, leaving
    # a dangling pointer behind. Stashing that pointer and freeing it a
    # visit later was therefore a plain double free. See the REVISION 34
    # note further up for the full evidence trail.
    #
    # The two earlier attempts documented here previously (freeing
    # immediately before the overwriting load, and calling
    # ResetAudioForLevelChange ourselves) were both variations on the
    # same non-problem, which is why neither could be made to work.


    instructions2 += emit_load_addr(3, sound_sam_path_addr)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CONVERT_PATH))
    instructions2 += [_cmpwi(3, -1)]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "hook2_sound_done"))
    instructions2.append(_mr(4, 3))
    instructions2.append(_li(3, 0x13))
    instructions2 += emit_load_donor_field(5, DTE_DONOR_SOUND_ID, 2)
    instructions2.append(_li(6, 0))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", QUEUE_ASYNC_FILE_LOAD))

    # REVISION 35: the flag write that used to sit here has moved UP to
    # immediately after the .pps queue above - see its own comment there
    # for why. Reaching this point means both loads were queued; a .sam
    # failure branches to hook2_sound_done with the flag already
    # correctly set by the .pps step, so the .pps buffer still gets
    # freed by the native cleanup loop.

    labels2["hook2_sound_done"] = len(instructions2)

    # --- REVISION 30: claim this record's own file_buffer tracking
    # slot (mirrors HOOK1's own identical step from before this whole
    # block moved here) - needed so EXIT_HOOK can find and free it
    # later, for whichever path (fresh MemAlloc) actually allocates
    # something. Uses HOOK2's own idx counter (donor_scratch_idx_addr,
    # not yet incremented for this record - that happens later, at
    # advance_idx). ---
    instructions2 += emit_load_mem_word(3, donor_scratch_idx_addr)
    instructions2.append(_rlwinm(3, 3, 2, 0, 29))  # idx * 4 via shift-left-2
    instructions2 += emit_load_addr(4, last_file_buffer_scratch_addr)
    instructions2 += [_add(5, 3, 4)]
    instructions2 += emit_store_mem_word(5, 6, current_file_buffer_slot_addr_addr)

    # --- REVISION 31: same idea, for CTM/texture-array/table_descriptor
    # tracking - moved here from HOOK1 alongside the CTM load itself
    # (below), so CTM can share HOOK2's own run-pooling scheme/cursor
    # with file_buffer instead of always doing a fresh MemAlloc. r3
    # still holds idx*4 from the file_buffer computation just above. ---
    instructions2 += emit_load_addr(4, last_ctm_buffer_scratch_addr)
    instructions2 += [_add(5, 3, 4)]
    instructions2 += emit_store_mem_word(5, 6, current_ctm_buffer_slot_addr_addr)

    instructions2 += emit_load_addr(4, last_resolved_texture_array_scratch_addr)
    instructions2 += [_add(5, 3, 4)]
    instructions2 += emit_store_mem_word(5, 6, current_resolved_texture_array_slot_addr_addr)

    # table_descriptor is a 12-byte (3-word) struct per slot, not 4 -
    # recompute idx * 12 separately (r3 above holds idx * 4).
    instructions2 += emit_load_mem_word(3, donor_scratch_idx_addr)
    instructions2 += [_li(4, 12), _mullw(3, 3, 4)]
    instructions2 += emit_load_addr(4, table_descriptor_scratch_addr)
    instructions2 += [_add(5, 3, 4)]
    instructions2 += emit_store_mem_word(5, 6, current_table_descriptor_addr_addr)

    # tag itself is a holdover name from when this label prefix was
    # shared with HOOK1 (now removed entirely - REVISION 32) - kept as
    # "hook1" rather than renamed, since renaming would mean touching
    # every f"{tag}_..." label reference throughout this whole model-
    # data section for no functional benefit; it's just a label-name
    # prefix now, with no other meaning.
    tag = "hook1"

    # === donor model data: format donor_level_id into the level path,
    # compute sector-aligned read params from donor_file_offset/size at
    # runtime (0x800 is a power of 2, so this is just masking/shifting,
    # no actual division needed - mirrors _compute_read_params() exactly). ===
    emit_format_digits_call_donor(fills2, instructions2, DTE_DONOR_LEVEL_ID, 1, donor_level_path_addr + DONOR_LEVEL_PATH_DIGITS_OFFSET, 2)

    instructions2 += emit_load_donor_field(3, DTE_DONOR_FILE_OFFSET, 3)
    instructions2 += emit_load_donor_field(4, DTE_DONOR_SIZE, 3)
    instructions2 += [
        _rlwinm(5, 3, 0, 0, 20),   # r5 = file_offset & 0xFFFFF800 = read_offset (aligned)
        _rlwinm(6, 3, 0, 21, 31),  # r6 = file_offset & 0x7FF = monster_offset_in_buffer (prefix)
        _add(7, 3, 4),             # r7 = file_offset + size = end
        _addi(7, 7, 0x7FF),
        _rlwinm(7, 7, 0, 0, 20),   # r7 = (end + 0x7FF) & 0xFFFFF800 = aligned_end
        _subf(8, 5, 7),            # r8 = aligned_end - read_offset = read_length
    ]
    instructions2 += emit_store_mem_word(5, 9, read_offset_var_addr)
    instructions2 += emit_store_mem_word(6, 9, monster_offset_var_addr)
    instructions2 += emit_store_mem_word(8, 9, read_length_var_addr)

    instructions2 += emit_load_addr(3, donor_level_path_addr)
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DVD_CONVERT_PATH))
    instructions2 += [
        _mr(29, 3),
        _cmpwi(3, -1),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_convert_failed"))

    instructions2 += [
        _mr(3, 29),
        _lis(4, hi(fileinfo_addr)),
        _ori(4, 4, lo(fileinfo_addr)),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DVD_FAST_OPEN))
    instructions2 += [_cmpwi(3, 0)]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_open_failed"))


    # --- REVISION 26: try reusing this level's own already-loaded
    # native monster space FIRST, before ever calling MemAlloc. Every
    # native monster is swapped 100% of the time, and its own
    # DecodeResourcePoolCategory setup already ran natively before any
    # of our own hooks execute - so a VERIFIED contiguous run's own
    # total space (see _find_contiguous_native_runs()'s own docstring)
    # is genuinely free real estate, at ZERO additional memory cost,
    # for as much of it as fits. Falls through to the EXISTING,
    # unchanged MemAlloc path below for anything that doesn't fit (or
    # has no verified-safe run at all, native_run_id == 0xFF). ---
    instructions2 += emit_load_field(3, REC_NATIVE_RUN_ID, 1)
    instructions2.append(_cmpwi(3, NO_RUN_AVAILABLE))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_use_fresh_alloc"))

    instructions2 += [_li(4, RUN_TABLE_ENTRY_SIZE), _mullw(4, 3, 4)]  # r4 = run_id * 6 (not a power of 2, needs a real multiply)
    instructions2 += emit_load_addr(5, run_table_addr)
    instructions2 += [_add(6, 4, 5), _addi(6, 6, 1)]  # r6 = run_table_addr + run_id*6 + 1 = this run's own entry start (past the 1-byte padding)
    instructions2.append(_lwz(7, -1, 6))               # r7 = word read 1 byte early (safely borrows the padding byte, or the previous entry's own last byte)
    instructions2.append(_rlwinm(7, 7, 0, 8, 31))       # r7 = start_offset (u24, masked)
    instructions2.append(_lwz(8, 2, 6))                 # r8 = word read starting at entry+2 (1 byte early for total_size, which starts at entry+3)
    instructions2.append(_rlwinm(8, 8, 0, 8, 31))       # r8 = total_size (u24, masked)

    instructions2.append(_rlwinm(9, 3, 2, 0, 29))  # r9 = run_id * 4 (cursor slot offset) - shift-left-2
    instructions2 += emit_load_addr(10, run_cursor_scratch_addr)
    instructions2 += [_add(11, 9, 10)]              # r11 = this run's own cursor slot address
    instructions2.append(_lwz(12, 0, 11))            # r12 = current cursor

    instructions2 += emit_load_mem_word(4, read_length_var_addr)
    instructions2.append(_add(4, 12, 4))            # r4 = candidate new cursor (current + needed)
    instructions2.append(_cmplw(8, 4))              # r8(total_size) < r4(candidate) -> doesn't fit
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "blt", f"{tag}_use_fresh_alloc"))

    # fits - compute address = LEVEL_DATA_BASE[runtime] + start_offset + old_cursor
    instructions2 += emit_load_addr(9, LEVEL_DATA_BASE_ADDR)
    instructions2.append(_lwz(9, 0, 9))             # r9 = level blob's own runtime base

    # --- SAFETY CHECK (fixing a real bug): the level's own big data
    # blob might not be loaded yet at the point THIS record's own HOOK1
    # processing runs (e.g. the very first level of a session) - if its
    # own runtime base pointer is still 0, using it would compute a
    # garbage/near-zero address and corrupt whatever's actually there.
    # Confirmed directly: a crash with "Invalid write to 0xfffffc18"
    # decodes to exactly -1000 in 32-bit signed arithmetic - i.e.
    # 0 - 1000, a NULL base plus a small offset, exactly what this
    # check prevents. Fall back to fresh MemAlloc instead. ---
    instructions2.append(_cmpwi(9, 0))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_use_fresh_alloc"))

    instructions2.append(_add(9, 9, 7))             # r9 += start_offset
    instructions2.append(_add(9, 9, 12))            # r9 += old cursor -> this record's own reused address
    instructions2.append(_stw(4, 0, 11))            # persist new cursor back to the run's own slot

    instructions2 += [
        _lis(6, hi(file_buffer_var_addr)),
        _ori(6, 6, lo(file_buffer_var_addr)),
        _stw(9, 0, 6),
        _mr(30, 9),
    ]
    # NOTE: deliberately NOT writing current_file_buffer_slot_addr_addr
    # here - this memory was never MemAlloc'd by us, so EXIT_HOOK must
    # never try to MEM_FREE it (that slot stays at its own zeroed
    # default from this visit's own reset, so EXIT_HOOK's "if nonzero,
    # free" check correctly skips it for this record).
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_file_buffer_acquired"))

    labels2[f"{tag}_use_fresh_alloc"] = len(instructions2)
    instructions2 += emit_load_mem_word(3, read_length_var_addr)
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", MEM_ALLOC))
    instructions2 += [
        _lis(6, hi(file_buffer_var_addr)),
        _ori(6, 6, lo(file_buffer_var_addr)),
        _stw(3, 0, 6),
        _mr(30, 3),
        _cmpwi(3, 0),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_memalloc_failed"))

    # --- REVISION 16: record THIS VISIT's own file_buffer pointer for
    # EXIT_HOOK to free at the real end of this same visit. ---
    instructions2 += emit_load_mem_word(4, current_file_buffer_slot_addr_addr)
    instructions2.append(_stw(3, 0, 4))

    labels2[f"{tag}_file_buffer_acquired"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
        _mr(4, 30),
    ]
    instructions2 += emit_load_mem_word(5, read_length_var_addr)
    instructions2 += emit_load_mem_word(6, read_offset_var_addr)
    instructions2 += [
        _lis(7, hi(callback_stub_addr)),
        _ori(7, 7, lo(callback_stub_addr)),
        _li(8, 2),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", ASYNC_READ))
    instructions2 += [_cmpwi(3, 0)]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "beq", f"{tag}_read_start_failed"))

    instructions2 += [
        _lis(3, hi(COMPLETION_FLAG_ADDR)),
        _ori(3, 3, lo(COMPLETION_FLAG_ADDR)),
        _li(4, 0),
        _stb(4, 0, 3),
    ]

    labels2[f"{tag}_poll_loop"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(COMPLETION_FLAG_ADDR)),
        _ori(3, 3, lo(COMPLETION_FLAG_ADDR)),
        _lbz(3, 0, 3),
        _cmpwi(3, 0),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bne", f"{tag}_poll_done"))

    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", CHECK_DVD_STATUS))
    instructions2 += [_cmpwi(3, 0)]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bne", f"{tag}_drive_ready"))

    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", MUTE_AUDIO))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_poll_continue"))

    labels2[f"{tag}_drive_ready"] = len(instructions2)
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", POLL_CONTROLLER))

    labels2[f"{tag}_poll_continue"] = len(instructions2)
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_poll_loop"))

    labels2[f"{tag}_poll_done"] = len(instructions2)
    instructions2 += [_mr(3, 30)]
    instructions2 += emit_load_mem_word(4, read_length_var_addr)
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DC_INVALIDATE))
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DVD_CLOSE))

    # donor_addr = file_buffer + monster_offset_in_buffer - left in r3,
    # ready for immediate use below (no scratch-array handoff needed
    # anymore - this is computed and consumed in the same pass now).
    instructions2 += [_mr(3, 30)]
    instructions2 += emit_load_mem_word(4, monster_offset_var_addr)
    instructions2.append(_add(3, 3, 4))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_model_load_done"))

    # --- model-load failure paths (best-effort, non-fatal - skip
    # ahead to this same record's own "done" point) ---
    labels2[f"{tag}_convert_failed"] = len(instructions2)
    instructions2.append(_li(3, 0))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_model_load_done"))

    labels2[f"{tag}_open_failed"] = len(instructions2)
    instructions2.append(_li(3, 0))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_model_load_done"))

    labels2[f"{tag}_memalloc_failed"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DVD_CLOSE))
    instructions2.append(_li(3, 0))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_model_load_done"))

    labels2[f"{tag}_read_start_failed"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "bl", DVD_CLOSE))
    instructions2.append(_li(3, 0))
    idx = len(instructions2)
    instructions2.append(None)
    fills2.append((idx, "b", f"{tag}_model_load_done"))

    labels2[f"{tag}_model_load_done"] = len(instructions2)


    # --- CRITICAL FIX (still applies, updated for REVISION 30): if
    # THIS record's own model-data load (now performed directly above,
    # within HOOK2 itself) failed - the pool's own capacity check
    # skipped it, the pool itself never allocated, or a genuine
    # DVD/MemAlloc failure - r3 was explicitly set to 0 by that
    # failure path. HOOK2 must NOT blindly write 0 into the target
    # slot and call DecodeResourcePoolCategory on it anyway. That
    # reads word[0] (0) plus a series of small fixed offsets, crashing
    # inside DecodeResourcePoolCategory itself - confirmed directly
    # against a real crash log (reads from 0x4, 0x8, 0xc... matching a
    # NULL base exactly). idx must still advance either way - it
    # indexes this record's own slot in every one of HOOK2's own
    # scratch arrays (last_ctm_buffer_scratch, last_file_buffer_
    # scratch, etc.), all sized/walked by EXIT_HOOK using this same,
    # unconditional-per-match sequence, regardless of whether this
    # specific record's own load succeeded - only the actual slot
    # write/DecodeResourcePoolCategory/word[8] sequence gets skipped
    # for a record whose own load failed. ---
    instructions2.append(_cmpwi(3, 0))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "advance_idx"))

    instructions2 += emit_load_target_slot_addr(4)
    instructions2.append(_stw(3, 0, 4))
    # REVISION 37: stash it - every later use in this record reloads
    # from here instead of recomputing (see the scratch's own note).
    instructions2 += emit_store_mem_word(4, 5, current_target_slot_addr_addr)
    instructions2.append(0x7C832378)  # mr r3, r4  (r3 = target_slot_addr, for DecodeResourcePoolCategory's own parameter)

    # --- REVISION 36c: THE ACTUAL LEAK FIX. DecodeResourcePoolCategory
    # ends by OVERWRITING resourceHandle[6] (byte offset 0x18) with a
    # fresh MemAlloc, without freeing whatever that field already held:
    #     if (*(ushort *)((int)resourceHandle + 10) != 0) {
    #       categoryValue = MemAlloc(... << 2);
    #       resourceHandle[6] = categoryValue;      // no free of the old value
    #     }
    # Native already decoded this same slot during its own level load
    # (allocating array A) before HOOK2 ever runs. Our decode call just
    # below therefore allocates array B and ORPHANS A - one leaked
    # native allocation per swapped monster, per level visit. That is
    # exactly the measured signature: one block per record, sized
    # (subCount << 2) so it varies by monster (~176-192 bytes), and
    # invisible to every MemAlloc breakpoint on this mechanic's own two
    # call sites because native allocated it.
    #
    # Freeing here first is precisely what native itself does before
    # re-loading a slot (FreeCardResourceSlot calls FreeLevelDataBuffer
    # on the slot before LoadCardResourceSlot re-decodes it). Safe and
    # idempotent: FreeLevelDataBuffer null-checks 0x18, frees it, and
    # zeroes the field, so a slot that was never decoded is a no-op.
    #
    # This is why REVISION 36/36b changed nothing: freeing at EXIT_HOOK
    # correctly releases B, but A was already orphaned back here. Both
    # halves are needed - this one stops the orphaning, and EXIT_HOOK's
    # own call still releases B at level exit. ---
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", FREE_LEVEL_DATA_BUFFER))
    instructions2 += emit_load_mem_word(3, current_target_slot_addr_addr)  # reload (REVISION 37)

    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DECODE_RESOURCE_POOL))

    instructions2 += emit_load_donor_field(3, DTE_DONOR_CARD_ID, 1)
    instructions2 += emit_load_mem_word(4, current_target_slot_addr_addr)
    instructions2.append(_sth(3, 8, 4))

    instructions2.append(_li(3, 0))
    instructions2 += emit_load_donor_field(4, DTE_DONOR_CARD_ID, 1)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", GET_OWNED_CARD_RECORD))

    # --- guard: GetOwnedCardRecord returns a "not found" sentinel for
    # a card the player doesn't currently own - which many random
    # donors won't be, especially early in a run. Observed crash
    # matched this exactly: 0xfffffbf8 (word[8] dereferenced later
    # during real gameplay) is precisely -0x408 as a signed 32-bit
    # value - consistent with a "not found -> index -1" pattern
    # (base + (-1 * a ~0x408-byte record stride), with base at/near
    # 0). A real pointer here is always in normal GC RAM ranges
    # (0x80xxxxxx-ish); a wrapped-negative value this large is not -
    # treat any return >= 0xFFF00000 (unsigned) as "not found" and
    # skip writing word[8] entirely for this record, rather than
    # blindly dereferencing and storing a wild pointer that only
    # crashes later, once real gameplay code reads it back. ---
    instructions2 += [
        _lis(6, 0xFFF0),
    ]
    instructions2.append(_cmplw(3, 6))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bge", "skip_levelstat_write"))

    instructions2 += [_lwz(5, 4, 3)]
    instructions2 += emit_load_mem_word(4, current_target_slot_addr_addr)
    instructions2.append(_stw(5, 0x20, 4))

    labels2["skip_levelstat_write"] = len(instructions2)

    # === REVISION 31: CTM/texture load - moved here from HOOK1 so it
    # can share the exact same run-pooling scheme/cursor as file_buffer
    # above, drawing from whatever capacity that record's own run has
    # LEFT after file_buffer's own consumption (not a separate, CTM-
    # only sub-pool) - falls back to fresh MemAlloc only once the
    # run's own total space is genuinely exhausted. Runs only if
    # file_buffer's own load above succeeded (see the "beq advance_idx"
    # check above this point) - a slot whose own core model-data write
    # got skipped has no use for texture data either. ===
    emit_format_digits_call_donor(fills2, instructions2, DTE_DONOR_CARD_ID, 1, ctm_path_addr + CTM_PATH_DIGITS_OFFSET, 3)

    instructions2 += emit_load_addr(3, ctm_path_addr)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CONVERT_PATH))
    instructions2 += [
        _mr(29, 3),
        _cmpwi(3, -1),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_open_failed"))

    instructions2 += [
        _mr(3, 29),
        _lis(4, hi(fileinfo_addr)),
        _ori(4, 4, lo(fileinfo_addr)),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_FAST_OPEN))
    instructions2 += [_cmpwi(3, 0)]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_open_failed"))

    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
        _lwz(3, DVDFILEINFO_SIZE_OFFSET, 3),
        _addi(3, 3, 0x1f),
        _rlwinm(3, 3, 0, 0, 26),
        _lis(6, hi(ctm_size_var_addr)),
        _ori(6, 6, lo(ctm_size_var_addr)),
        _stw(3, 0, 6),
    ]

    # --- try the SAME run pool file_buffer just used, continuing from
    # wherever its own consumption left the cursor (re-load run_id
    # fresh - r3-r12 aren't preserved across the several bl calls made
    # since file_buffer's own copy of this same value). ---
    instructions2 += emit_load_field(3, REC_NATIVE_RUN_ID, 1)
    instructions2.append(_cmpwi(3, NO_RUN_AVAILABLE))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_use_fresh_alloc"))

    instructions2 += [_li(4, RUN_TABLE_ENTRY_SIZE), _mullw(4, 3, 4)]
    instructions2 += emit_load_addr(5, run_table_addr)
    instructions2 += [_add(6, 4, 5), _addi(6, 6, 1)]
    instructions2.append(_lwz(7, -1, 6))
    instructions2.append(_rlwinm(7, 7, 0, 8, 31))       # r7 = start_offset
    instructions2.append(_lwz(8, 2, 6))
    instructions2.append(_rlwinm(8, 8, 0, 8, 31))       # r8 = total_size

    instructions2.append(_rlwinm(9, 3, 2, 0, 29))       # r9 = run_id * 4
    instructions2 += emit_load_addr(10, run_cursor_scratch_addr)
    instructions2 += [_add(11, 9, 10)]                   # r11 = this run's own cursor slot address
    instructions2.append(_lwz(12, 0, 11))                # r12 = current cursor (whatever file_buffer left it at)

    instructions2 += emit_load_mem_word(4, ctm_size_var_addr)
    instructions2.append(_add(4, 12, 4))                 # r4 = candidate new cursor
    instructions2.append(_cmplw(8, 4))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "blt", "ctm_use_fresh_alloc"))

    instructions2 += emit_load_addr(9, LEVEL_DATA_BASE_ADDR)
    instructions2.append(_lwz(9, 0, 9))
    instructions2.append(_cmpwi(9, 0))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_use_fresh_alloc"))

    instructions2.append(_add(9, 9, 7))                  # r9 += start_offset
    instructions2.append(_add(9, 9, 12))                 # r9 += old cursor -> this record's own reused address
    instructions2.append(_stw(4, 0, 11))                 # persist new cursor

    instructions2 += [
        _lis(6, hi(ctm_buffer_var_addr)),
        _ori(6, 6, lo(ctm_buffer_var_addr)),
        _stw(9, 0, 6),
        _mr(30, 9),
    ]
    # NOTE: deliberately NOT writing current_ctm_buffer_slot_addr_addr
    # here - same reasoning as file_buffer's own identical note above:
    # this memory was never MemAlloc'd by us, so EXIT_HOOK must never
    # try to MEM_FREE it.
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_buffer_acquired"))

    labels2["ctm_use_fresh_alloc"] = len(instructions2)
    instructions2 += emit_load_mem_word(3, ctm_size_var_addr)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", MEM_ALLOC))
    instructions2 += [
        _lis(6, hi(ctm_buffer_var_addr)),
        _ori(6, 6, lo(ctm_buffer_var_addr)),
        _stw(3, 0, 6),
        _mr(30, 3),
        _cmpwi(3, 0),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_memalloc_failed"))

    instructions2 += emit_load_mem_word(4, current_ctm_buffer_slot_addr_addr)
    instructions2.append(_stw(3, 0, 4))

    labels2["ctm_buffer_acquired"] = len(instructions2)
    instructions2 += [
        _mr(3, 29),
        _lis(4, hi(fileinfo_addr)),
        _ori(4, 4, lo(fileinfo_addr)),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_FAST_OPEN))
    instructions2 += [_cmpwi(3, 0)]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_read_start_failed"))

    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
        _mr(4, 30),
    ]
    instructions2 += emit_load_mem_word(5, ctm_size_var_addr)
    instructions2 += [
        _li(6, 0),
        _lis(7, hi(callback_stub_addr)),
        _ori(7, 7, lo(callback_stub_addr)),
        _li(8, 2),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", ASYNC_READ))
    instructions2 += [_cmpwi(3, 0)]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "beq", "ctm_read_start_failed"))

    instructions2 += [
        _lis(3, hi(COMPLETION_FLAG_ADDR)),
        _ori(3, 3, lo(COMPLETION_FLAG_ADDR)),
        _li(4, 0),
        _stb(4, 0, 3),
    ]

    labels2["ctm_poll_loop"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(COMPLETION_FLAG_ADDR)),
        _ori(3, 3, lo(COMPLETION_FLAG_ADDR)),
        _lbz(3, 0, 3),
        _cmpwi(3, 0),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bne", "ctm_poll_done"))

    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", CHECK_DVD_STATUS))
    instructions2 += [_cmpwi(3, 0)]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bne", "ctm_drive_ready"))

    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", MUTE_AUDIO))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_poll_continue"))

    labels2["ctm_drive_ready"] = len(instructions2)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", POLL_CONTROLLER))

    labels2["ctm_poll_continue"] = len(instructions2)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_poll_loop"))

    labels2["ctm_poll_done"] = len(instructions2)
    instructions2 += [
        _mr(3, 30),
        _lis(4, hi(ctm_size_var_addr)),
        _ori(4, 4, lo(ctm_size_var_addr)),
        _lwz(4, 0, 4),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DC_INVALIDATE))
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CLOSE))

    instructions2 += [
        _mr(3, 30),
        _lwz(4, 8, 30),
        _add(3, 3, 4),
    ]
    instructions2 += emit_load_mem_word(4, current_table_descriptor_addr_addr)
    instructions2 += [
        _stw(3, 4, 4),
        _mr(3, 4),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", LOAD_ENTITY_ANIMATION_TABLE))

    instructions2 += emit_load_mem_word(3, current_table_descriptor_addr_addr)
    instructions2.append(_lwz(3, 8, 3))
    instructions2 += emit_load_mem_word(4, current_resolved_texture_array_slot_addr_addr)
    instructions2.append(_stw(3, 0, 4))

    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_done"))

    # --- ctm-load failure paths (best-effort, non-fatal) ---
    labels2["ctm_open_failed"] = len(instructions2)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_done"))

    labels2["ctm_memalloc_failed"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CLOSE))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_done"))

    labels2["ctm_read_start_failed"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(fileinfo_addr)),
        _ori(3, 3, lo(fileinfo_addr)),
    ]
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "bl", DVD_CLOSE))
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "ctm_done"))

    labels2["ctm_done"] = len(instructions2)

    labels2["advance_idx"] = len(instructions2)
    # increment donor_scratch_idx (only for records that actually matched)
    instructions2 += emit_load_mem_word(6, donor_scratch_idx_addr)
    instructions2.append(_addi(6, 6, 1))
    instructions2 += emit_store_mem_word(6, 7, donor_scratch_idx_addr)

    labels2["next_record"] = len(instructions2)
    instructions2 += emit_load_mem_word(3, current_record_ptr_addr)
    instructions2.append(_addi(3, 3, RECORD_SIZE))
    instructions2 += emit_store_mem_word(3, 4, current_record_ptr_addr)
    idx2 = len(instructions2)
    instructions2.append(None)
    fills2.append((idx2, "b", "loop_top"))

    labels2["loop_done"] = len(instructions2)
    instructions2 += [
        _lis(3, hi(lr_save_addr)),
        _ori(3, 3, lo(lr_save_addr)),
        _lwz(3, 0, 3),
        _mtlr(3),
        _lis(3, hi(r29_save_addr)),
        _ori(3, 3, lo(r29_save_addr)),
        _lwz(29, 0, 3),
        _lis(3, hi(r30_save_addr)),
        _ori(3, 3, lo(r30_save_addr)),
        _lwz(30, 0, 3),
        ORIGINAL_HOOK2_INSTRUCTION,
        0x4E800020,  # blr
    ]

    total_words2 = len(instructions2)
    stub2_addr = patcher.alloc_cave(total_words2 * 4)

    # branch_makers itself used to be defined once, in HOOK1's own now-
    # removed code (REVISION 32), and reused here (and in EXIT_HOOK's
    # own, later fills-resolution loop) purely because Python functions
    # share one scope - moved here since this is now the first place
    # it's actually needed.
    branch_makers = {
        "b": _b,
        "bl": None,
        "beq": _beq,
        "bne": _bne,
        "bge": _bge,
        "bdnz": _bdnz,
        "blt": _blt,
        "bgt": _bgt,
    }

    for f_idx, kind, target in fills2:
        from_addr = stub2_addr + f_idx * 4
        if kind == "bl":
            instructions2[f_idx] = patcher.make_bl(from_addr, target)
        else:
            to_addr = stub2_addr + labels2[target] * 4
            instructions2[f_idx] = branch_makers[kind](from_addr, to_addr)

    patcher.write_code(stub2_addr, instructions2)
    patcher.write_branch(HOOK2_ADDR, stub2_addr, link=True)
    logger.info(f"[mechanic_randomize_monsters] stub2_addr = {hex(stub2_addr)}")
    logger.info(f"[mechanic_randomize_monsters] HOOK2_ADDR = {hex(HOOK2_ADDR)} (patched to bl {hex(stub2_addr)})")

    # ================================================================
    # EXIT_HOOK stub (REVISION 16): the real level-exit point (see
    # EXIT_HOOK_ADDR's own docstring note above). Walks the SAME
    # record table one more time; for each record whose own
    # target_level_id matches the level that was JUST played (still
    # the current LEVEL_ID_ADDR value at this point, since main()'s
    # own cleanup sequence runs before anything changes it for the
    # next iteration), frees whatever ctm_buffer/file_buffer THIS
    # visit's own HOOK1 tracked - nothing more (levels never touched
    # this visit have nothing tracked to free), nothing less (every
    # matching record's own tracked buffer gets freed, not just some).
    # Much simpler than HOOK1/HOOK2 - no DVD/async work here, so no
    # need for r29/r30 at all, just LR (since our own internal "bl"
    # calls to MEM_FREE would otherwise clobber the return address the
    # ORIGINAL "bl EXIT_HOOK_ADDR" call set for us).
    # ================================================================
    instructions3 = [
        _mflr(0),
        _lis(3, hi(lr_save_addr)),
        _ori(3, 3, lo(lr_save_addr)),
        _stw(0, 0, 3),
    ]

    fills3 = []
    labels3 = {}

    # REVERTED: an earlier version of this file called the game's own
    # ResetAudioForLevelChange(levelId) here directly. Confirmed via
    # main_dol.c this function is ALREADY called automatically, as
    # part of every native level transition (LoadLevelAndShowLoading
    # Screen's own cleanup sequence) - critically, that native call
    # happens well AFTER the new level's own InitLevelAudioAndCamera/
    # RunLevelEntryScriptSync have already run, giving HOOK2's own
    # just-queued async sound loads (0x16/0x13, queued via
    # QueueAsyncFileLoad) time to actually be processed and have their
    # own buffer pointer fields populated. Confirmed via main_dol.c
    # that a queued async load's own buffer pointer gets allocated
    # only once the async-load-queue PROCESSOR reaches that specific
    # entry (ProcessAsyncLoadQueue) - not instantly when queued, and
    # not guaranteed to have happened yet by the time EXIT_HOOK runs
    # (which fires right as the player leaves the level, potentially
    # very soon after HOOK2 just queued a whole batch of new sound
    # loads for it). Calling ResetAudioForLevelChange from here risked
    # freeing a sound slot's own buffer-pointer field before the async
    # queue had processed it - i.e. freeing genuine uninitialized
    # garbage, not a real pointer - corrupting the memory arena's own
    # free-list immediately, with the resulting crash only surfacing
    # later, whenever some unrelated allocation next stumbled into the
    # now-corrupted structure (confirmed: this exact pattern crashed
    # while loading the NEXT level, not at the point of the bad free
    # itself). Relying on the native, automatic call instead avoids
    # this race entirely.

    instructions3 += emit_load_addr(3, records_addr)
    instructions3 += emit_store_mem_word(3, 4, current_record_ptr_addr)
    instructions3.append(_li(3, 0))
    instructions3 += emit_store_mem_word(3, 4, exit_scratch_idx_addr)

    labels3["loop_top"] = len(instructions3)
    instructions3 += emit_load_mem_word(3, current_record_ptr_addr)
    instructions3 += emit_load_addr(4, records_end_addr)
    instructions3.append(_cmplw(3, 4))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "bge", "loop_done"))

    instructions3 += emit_load_field(5, REC_TARGET_LEVEL_ID, 1)
    instructions3 += emit_load_addr(6, LEVEL_ID_ADDR)
    instructions3.append(_lbz(6, 0, 6))
    instructions3.append(_cmplw(5, 6))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "bne", "next_record"))

    # this record matched - compute idx*4, use it for both tracking arrays
    instructions3 += emit_load_mem_word(3, exit_scratch_idx_addr)
    instructions3.append(_rlwinm(3, 3, 2, 0, 29))  # idx * 4 via shift-left-2

    # REMOVED (per explicit request): the flag=3 sound-slot marking
    # block that used to run here. Precise interaction with several
    # pieces of native code was never fully, confidently established
    # via static analysis alone, and live debugging to pin it down
    # further wasn't a good fit here (the relevant addresses are all
    # high-frequency, constantly-executing OS/scheduler code, where
    # execution breakpoints aren't practically usable, and a targeted
    # memory write-breakpoint on the one concrete hypothesis tested -
    # SelectThread's own function-pointer table entry - never fired).
    # Removed entirely rather than keep a mechanism whose own full
    # behavior alongside native code isn't precisely understood.

    # free ctm_buffer_scratch[idx] if nonzero
    instructions3 += emit_load_addr(4, last_ctm_buffer_scratch_addr)
    instructions3 += [_add(5, 3, 4), _lwz(5, 0, 5)]
    instructions3.append(_cmpwi(5, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_ctm_free"))
    emit_mem_free(fills3, instructions3, 5)
    labels3["skip_ctm_free"] = len(instructions3)

    # free file_buffer_scratch[idx] if nonzero (recompute idx*4 - r3
    # may have been clobbered by the MemFree call just made above)
    instructions3 += emit_load_mem_word(3, exit_scratch_idx_addr)
    instructions3.append(_rlwinm(3, 3, 2, 0, 29))  # idx * 4 via shift-left-2
    instructions3 += emit_load_addr(4, last_file_buffer_scratch_addr)
    instructions3 += [_add(5, 3, 4), _lwz(5, 0, 5)]
    instructions3.append(_cmpwi(5, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_file_free"))
    emit_mem_free(fills3, instructions3, 5)
    labels3["skip_file_free"] = len(instructions3)

    # --- REVISION 18: before freeing the resolved-texture array,
    # walk its own entries and reset each texture's own cache slot
    # (byte 0 of its 0x3c-byte entry in CACHE_ENTRY_TABLE_ADDR) plus
    # its hash-table entry (HASH_TABLE_ADDR) back to free/0 - otherwise
    # the cache slot is leaked forever and the next load of this same
    # donor keeps finding a stale hash entry pointing at data we've
    # since freed (see CACHE_ENTRY_TABLE_ADDR's own docstring note). ---
    instructions3 += emit_load_mem_word(3, exit_scratch_idx_addr)
    instructions3 += [_li(4, 12), _mullw(3, 3, 4)]
    instructions3 += emit_load_addr(4, table_descriptor_scratch_addr)
    instructions3 += [_add(6, 3, 4)]  # r6 = this record's own table_descriptor addr
    instructions3.append(_lwz(3, 0, 6))  # r3 = texture count
    instructions3.append(_cmpwi(3, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_cache_cleanup"))

    instructions3.append(_lwz(7, 8, 6))  # r7 = array_ptr (tableDescriptor[2])
    instructions3.append(_cmpwi(7, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_cache_cleanup"))

    instructions3.append(_mtctr(3))  # loop `count` times - safe, no bl calls inside
    labels3["cache_cleanup_loop"] = len(instructions3)
    instructions3.append(_lwz(8, 0, 7))  # r8 = cacheEntryScan (this texture's own cache-entry pointer)
    instructions3.append(_cmpwi(8, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_this_cache_entry"))
    instructions3 += [
        _li(9, 0),
        _stb(9, 0, 8),   # cacheEntryScan[0] = 0 (mark slot free again)
        _lhz(9, 2, 8),   # r9 = hash = *(u16*)(cacheEntryScan+2)
        _li(10, 4),
        _mullw(9, 9, 10),
    ]
    instructions3 += emit_load_addr(10, HASH_TABLE_ADDR)
    instructions3 += [
        _add(9, 9, 10),
        _li(10, 0),
        _stw(10, 0, 9),  # HASH_TABLE_ADDR[hash] = 0
    ]
    labels3["skip_this_cache_entry"] = len(instructions3)
    instructions3.append(_addi(7, 7, 4))  # advance to next array entry
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "bdnz", "cache_cleanup_loop"))

    labels3["skip_cache_cleanup"] = len(instructions3)

    # free resolved_texture_array_scratch[idx] if nonzero (REVISION 17
    # - tableDescriptor[2], LoadEntityAnimationTable's own internal
    # allocation, previously invisible to us and never freed at all)
    instructions3 += emit_load_mem_word(3, exit_scratch_idx_addr)
    instructions3.append(_rlwinm(3, 3, 2, 0, 29))  # idx * 4 via shift-left-2
    instructions3 += emit_load_addr(4, last_resolved_texture_array_scratch_addr)
    instructions3 += [_add(5, 3, 4), _lwz(5, 0, 5)]
    instructions3.append(_cmpwi(5, 0))
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "beq", "skip_texture_array_free"))
    emit_mem_free(fills3, instructions3, 5)
    labels3["skip_texture_array_free"] = len(instructions3)

    instructions3 += emit_load_mem_word(3, exit_scratch_idx_addr)
    instructions3.append(_addi(3, 3, 1))
    instructions3 += emit_store_mem_word(3, 4, exit_scratch_idx_addr)

    labels3["next_record"] = len(instructions3)
    instructions3 += emit_load_mem_word(3, current_record_ptr_addr)
    instructions3.append(_addi(3, 3, RECORD_SIZE))
    instructions3 += emit_store_mem_word(3, 4, current_record_ptr_addr)
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "b", "loop_top"))

    labels3["loop_done"] = len(instructions3)
    instructions3 += [
        _lis(3, hi(lr_save_addr)),
        _ori(3, 3, lo(lr_save_addr)),
        _lwz(3, 0, 3),
        _mtlr(3),
    ]
    idx3 = len(instructions3)
    instructions3.append(None)
    fills3.append((idx3, "b", DEACTIVATE_ALL_ENTITIES_ADDR))

    total_words3 = len(instructions3)
    stub3_addr = patcher.alloc_cave(total_words3 * 4)

    for f_idx, kind, target in fills3:
        from_addr = stub3_addr + f_idx * 4
        if kind == "bl":
            if isinstance(target, str):
                to_addr = stub3_addr + labels3[target] * 4
                instructions3[f_idx] = patcher.make_bl(from_addr, to_addr)
            else:
                instructions3[f_idx] = patcher.make_bl(from_addr, target)
        elif kind == "b" and not isinstance(target, str):
            # tail call to a fixed absolute-ish target (DEACTIVATE_ALL_ENTITIES_ADDR) -
            # encode as a relative "b", same displacement math as make_bl but without linking
            instructions3[f_idx] = _b(from_addr, target)
        else:
            to_addr = stub3_addr + labels3[target] * 4
            instructions3[f_idx] = branch_makers[kind](from_addr, to_addr)

    patcher.write_code(stub3_addr, instructions3)
    patcher.write_branch(EXIT_HOOK_ADDR, stub3_addr, link=True)
    logger.info(f"[mechanic_randomize_monsters] stub3_addr = {hex(stub3_addr)}")
    logger.info(f"[mechanic_randomize_monsters] EXIT_HOOK_ADDR = {hex(EXIT_HOOK_ADDR)} (patched to bl {hex(stub3_addr)})")

    # ================================================================
    # FUN_80130ce8 native bugfix - see FUN_80130CE8_CRASH_LABEL_ADDR's
    # own comment (near this file's other hook-point constants) for
    # the full rationale. Entirely independent of the HOOK/HOOK2/
    # EXIT_HOOK record-processing trio above.
    #
    # Single-instruction, same-size trampoline: FUN_80130CE8_CRASH_
    # LABEL_ADDR (currently "lhz r0, 2(r31)") gets overwritten with a
    # branch to fun_80130ce8_fix_addr below - nothing after it in
    # main.dol shifts, since one 4-byte instruction is replaced with
    # another 4-byte instruction, not inserted alongside it.
    # ================================================================
    fun_80130ce8_fix_instructions = [
        _cmpwi(31, 0),
        None,  # beq safe_return - filled in below once fun_80130ce8_fix_addr is known
        _lhz(0, 2, 31),  # re-execute the original, displaced instruction
        None,  # b FUN_80130CE8_RESUME_ADDR - filled in below
        None,  # safe_return: b FUN_80130CE8_SAFE_EPILOGUE_ADDR - filled in below
    ]
    fun_80130ce8_fix_addr = patcher.alloc_cave(len(fun_80130ce8_fix_instructions) * 4)
    fun_80130ce8_fix_instructions[1] = _beq(fun_80130ce8_fix_addr + 4, fun_80130ce8_fix_addr + 16)
    fun_80130ce8_fix_instructions[3] = _b(fun_80130ce8_fix_addr + 12, FUN_80130CE8_RESUME_ADDR)
    fun_80130ce8_fix_instructions[4] = _b(fun_80130ce8_fix_addr + 16, FUN_80130CE8_SAFE_EPILOGUE_ADDR)
    patcher.write_code(fun_80130ce8_fix_addr, fun_80130ce8_fix_instructions)
    patcher.write_branch(FUN_80130CE8_CRASH_LABEL_ADDR, fun_80130ce8_fix_addr, link=False)
    logger.info(f"[mechanic_randomize_monsters] fun_80130ce8_fix_addr = {hex(fun_80130ce8_fix_addr)}")
    logger.info(f"[mechanic_randomize_monsters] FUN_80130CE8_CRASH_LABEL_ADDR = {hex(FUN_80130CE8_CRASH_LABEL_ADDR)} (patched to b {hex(fun_80130ce8_fix_addr)})")

    # ================================================================
    # FUN_8012fda0 native bugfix - see FUN_8012FDA0_HOOK_ADDR's own
    # comment (near this file's other hook-point constants) for the
    # full rationale. The actual, unified root cause behind both this
    # crash and the FUN_80130ce8 one fixed just above.
    #
    # Same single-instruction, same-size trampoline pattern: FUN_8012
    # FDA0_HOOK_ADDR (currently "stw r30, 8(r1)") gets overwritten with
    # a branch to fun_8012fda0_fix_addr below.
    # ================================================================
    fun_8012fda0_fix_instructions = [
        _cmpwi(31, 0),
        None,  # beq safe_return - filled in below once fun_8012fda0_fix_addr is known
        _stw(30, 8, 1),  # re-execute the original, displaced instruction
        None,  # b FUN_8012FDA0_RESUME_ADDR - filled in below
        # safe_return: unwind the small, partial stack frame this
        # function's own prologue already built, then return 0 -
        # matching its own, existing "not found / table full" return
        # value - without ever entering the critical section, since we
        # bail out before that call ever happens.
        _lwz(31, FUN_8012FDA0_R31_SAVE_OFFSET, 1),
        _lwz(0, FUN_8012FDA0_LR_SAVE_OFFSET, 1),
        _mtlr(0),
        _addi(1, 1, FUN_8012FDA0_FRAME_SIZE),
        _li(3, 0),
        0x4E800020,  # blr
    ]
    fun_8012fda0_fix_addr = patcher.alloc_cave(len(fun_8012fda0_fix_instructions) * 4)
    fun_8012fda0_fix_instructions[1] = _beq(fun_8012fda0_fix_addr + 4, fun_8012fda0_fix_addr + 16)
    fun_8012fda0_fix_instructions[3] = _b(fun_8012fda0_fix_addr + 12, FUN_8012FDA0_RESUME_ADDR)
    patcher.write_code(fun_8012fda0_fix_addr, fun_8012fda0_fix_instructions)
    patcher.write_branch(FUN_8012FDA0_HOOK_ADDR, fun_8012fda0_fix_addr, link=False)
    logger.info(f"[mechanic_randomize_monsters] fun_8012fda0_fix_addr = {hex(fun_8012fda0_fix_addr)}")
    logger.info(f"[mechanic_randomize_monsters] FUN_8012FDA0_HOOK_ADDR = {hex(FUN_8012FDA0_HOOK_ADDR)} (patched to b {hex(fun_8012fda0_fix_addr)})")

    # REVERTED (per explicit request): the LoadShopUIElement entry-
    # point guard that used to be installed here. Its own crash-test
    # (end of level 1, PC within FUN_8013992c) turned out NOT to be
    # caused by this fix at all - FUN_8013992c is only ever reached
    # via ResetAudioForLevelChange's own native cleanup loop, a
    # completely different code path this guard never touched - but
    # removed anyway per explicit preference, in favor of directly
    # fixing the two, now-identified underlying issues instead (see
    # the flag=3 marking system and the DAT_80275cd4 buffer-leak fix,
    # both re-added below).