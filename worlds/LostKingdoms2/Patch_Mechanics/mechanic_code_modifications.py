"""
Foundational code patches that redirect several of the game's own systems
through a shared external trigger address (0x8025D014, inside the same
"unused buffer" region as KEY_ITEM_LOCATION_ADDRESS/ITEM_INDEX_ADDRESS/
SHOP_LOCATION_ADDRESS), plus one unrelated fix to shop card generation.
Unconditional - these are foundational to how the AP client communicates
with the game, not tied to any specific randomizer option.

Traced from the original LK2Generator.py's modify_code() raw instruction
patches. Each patch replaces one or more original instructions - the
original bytes are read directly from the clean ISO/DOL at build time
(via ORIGINAL_INSTRUCTIONS below) rather than hardcoded, so this stays
correct if this ever needs to be re-derived against a different revision.

--- Group 1: SetKeyItemObtained ---
Redirects the write path only (game's own key-item-granted logic, e.g.
awarding Keil Runestone for defeating the Stranger) to write directly into
key_item_location (0x8025e652, from LK2Client.STORAGE_ADDRESSES) as a
bitmask, instead of the real per-bit bitmask at player-struct offset 0x5c.
This makes "the game just granted a key item" into a check-completion
signal the AP client can watch for, decoupled from actually unlocking
anything, AND lets our own opcode 499 (mechanic_ap_key_item_opcode.py)
read it back for AP-location-based spawn checks. GetKeyItemObtained (the
read path, used by door checks) is deliberately left unpatched - doors
check the real bitmask, fully vanilla. The AP client is responsible for
writing the real bitmask directly when the corresponding item is actually
received from AP.

NOTE: this redirects the function's base-address computation itself (not
just the final offset), since key_item_location is a standalone bitmask
address unrelated to the player-struct layout. The function also folds in
(keyItemId>>5)*4 + playerIndex*0x6c onto this base before the read/write -
harmless no-op for our actual usage (all current key item IDs are <32,
always called with playerIndex=0), but worth keeping in mind if a key
item ID >=32 or a playerIndex-1 grant is ever introduced.

--- Group 2: SelectCameraFocusTarget ---
--- Group 3: GetEventFlag ---
Both redirect a check that would normally read a real story-progress event
flag to instead read the shared trigger byte (0x8025D014) - used to control
Magic Booster activation externally rather than through normal story flags.

--- Group 4: BuildShopInventory ---
NOPs out a conditional branch that guards the game's own duplicate-card
exclusion check in shop generation, removing that restriction so the shop
randomization mechanic has the full, unrestricted card pool to work with.

--- Group 5: SelectCameraMode ---
The "levelId==1 && hasSeenOpeningCutscene==0" branch normally sets
cameraMode=5, which reserves only 5 of the 10 card-model buffer slots
(SelectCameraMode/GetOrAllocateCardModelBuffer/AllocateCardModelSlot only
ever allocate/search slots [cameraMode..9]). The Stranger's deck needs
exactly 5 simultaneous slots, leaving zero margin - reachable via AP's
door redirect before the level is normally beaten, this overflows and
crashes. Changing this branch to cameraMode=1 reserves 9 of the 10 slots
instead - still comfortably covers the Stranger's own 5-slot need with
margin to spare, while allocating one fewer slot than cameraMode=0.
cameraMode=0 (reserving all 10 slots) was tried first and confirmed to
itself cause a different crash on level 1 completion when combined with
deck/enemy randomization - apparently over-allocating this pool's own
memory footprint competes with something else's memory needs under that
combination, even though the pool's own per-slot contents were otherwise
unaffected. cameraMode=1 was confirmed in-game to resolve both issues.
Confirmed cameraMode is used exclusively for this buffer pool - no effect
on encounter spawning or anything else.

--- Group 6: placeholder-card popup text (card ID 0 / "ダミー") ---
When a card ID of 0 is granted (matches how AP-controlled chests are set
up - see mechanic_disable_vanilla_chests.py's own docstring), the "you
have found the ___ card!" popup shows the raw internal placeholder name
("ダミー", Japanese for "dummy") instead of a real card name, since card 0
was never meant to be actually obtained in normal play.

Traced directly: StartDialogueDisplay -> ResolveDialogueMessageID (for a
messageCode in the 1000-1999 range) builds this message via
GetUIText(2,3) ("You have found\nthe %s card!") and GetUIText(0x17,
messageCode-1000) (the card's own name) into a single sprintf call. Both
strings are runtime-loaded from a separate DVD file, game/rune.pdm - not
embedded in the DOL/executable at all, so these are raw ISO byte writes
against that file's own known ISO offset (RUNE_PDM_ISO_OFFSET), not
patcher.patch_word() instruction patches like Groups 1-5 above.

Both replacements were chosen to fit the EXISTING string's own byte
budget with no structural changes needed - confirmed directly against
the extracted file: strings in this table are tightly packed,
null-terminated, with zero slack space between entries (the gap to the
very next entry's own name, "Skeleton" for table 0x17, is exactly 6
bytes + 1 null terminator - nothing to spare). "AP" (2 bytes + null) is
comfortably shorter than "ダミー" (6 bytes), so it's a safe in-place
patch. The message template itself ("You have found\nthe %s card!" ->
"You have found\nan %s Item!") is patched as ONE full-string
replacement rather than two separate, position-dependent sub-patches
for "the"->"an" and "card"->"Item" - since "an" is 1 byte shorter than
"the", editing it in isolation would shift everything after it,
including "Item", out of position. The new string (26 bytes) is 1 byte
shorter than the original (27 bytes), fitting safely with one byte to
spare. Both card ID 0's OTHER name-table entries (tables 0x11/0x12,
used by the separate card catalog/collection screen, a different
function entirely) still show "ダミー" if viewed there - not touched by
this, since only the chest-pickup popup was reported as an issue.

--- Group 7: allow the A button to dismiss the placeholder-card popup ---
Only B closes the "found a card" popup for card ID 0 - A does nothing at
all. Traced via extensive live memory watching (StartDialogueDisplay's
own internal state variables at 0x8017927c/0x8017927d/0x8017927e/
0x8017927f/0x80179284 - all confirmed to never change while A is held,
despite StartDialogueDisplay itself confirmed via breakpoint to be
called repeatedly). Root cause: ProcessWorldInteraction's own "A held"
branch calls StartDialogueDisplay(*(byte*)(currentInteractionTarget+1))
- the RAW card ID, no offset added (unlike the +1000/+2000/+3000 used
by the initial "open" call elsewhere) - and StartDialogueDisplay's own
very first line is "if (messageCode != 0) { ...entire function body... }".
For card ID 0, messageCode is 0, so this guard is true and the ENTIRE
function silently no-ops, every single time A is pressed - explaining
why none of its internal state ever changes. For any nonzero card ID,
this guard passes normally and A works exactly as it always has.

NOPs the beq at 0x80024854 (the branch implementing this guard,
confirmed via direct disassembly: cmplwi r3,0 at 0x80024840, beq
LAB_80024ccc at 0x80024854) - now the function's own body always runs
regardless of messageCode's own value. Deliberately NOT changed at the
ProcessWorldInteraction call site itself (would need a small hook/
trampoline to substitute a safe nonzero value only for card ID 0,
preserving other legitimate raw-value callers exactly as-is) - this is
the simpler, single-instruction alternative, accepted with one known,
narrow tradeoff: at least one OTHER caller (dialogueCategory==0xca,
StartDialogueDisplay((uint)*(byte*)(currentInteractionTarget+4)), a
different, rarer interaction type) also passes its own value with no
offset added, and could in principle rely on genuinely passing 0 to
mean "nothing to show" for that specific case. No such instance is
confirmed to exist in practice - flagged here for future reference in
case something in that specific interaction type ever behaves
unexpectedly.
"""

# (address, new_instruction) pairs, grouped to match the explanation above.
PATCHES = [
    # --- Group 1: SetKeyItemObtained (write path only - see docstring) ---
    (0x8006e774, 0x38a5e652),  # addi r5, r5, -12276 (base=0x8025d00c) -> addi r5, r5, -6574 (base=0x8025e652)
    (0x8006e78c, 0x80850000),  # lwz r4, 92(r5) -> lwz r4, 0(r5)
    (0x8006e798, 0x90050000),  # stw r0, 92(r5) -> stw r0, 0(r5)

    # --- Group 2: SelectCameraFocusTarget (Magic Booster trigger) ---
    (0x80075738, 0x3C808026),  # lis r4, 0x8026              (unchanged - same bytes as original)
    (0x8007573c, 0x8004D014),  # addi r4, r4, -9268          -> lwz r0, -12268(r4)  [reads 0x8025D014]
    (0x80075740, 0x60000000),  # lwz r0, 452(r4)             -> NOP (now-redundant second load)

    # --- Group 3: GetEventFlag (Magic Booster trigger) ---
    (0x8007b334, 0x3C608026),  # addi r4, r0, 1              -> lis r3, 0x8026
    (0x8007b338, 0x8003D014),  # lwz r0, 4(r3)               -> lwz r0, -12268(r3)  [reads 0x8025D014]

    # --- Group 4: BuildShopInventory (remove duplicate-card exclusion check) ---
    (0x800dc438, 0x60000000),  # bc ... (conditional branch) -> NOP

    # --- Group 5: SelectCameraMode (Stranger card-buffer pool fix) ---
    (0x80054d60, 0x38000001),  # addi r0, r0, 5 (cameraMode=5) -> addi r0, r0, 1 (cameraMode=1)

    # --- Group 7: allow A to dismiss the placeholder-card popup ---
    (0x80024854, 0x60000000),  # beq LAB_80024ccc (messageCode==0 guard) -> NOP
]

# --- Group 6: placeholder-card popup text - raw ISO byte patches against
# game/rune.pdm (see docstring above for the full trace/rationale). Each
# entry: (iso_offset, expected_original_bytes, new_bytes). expected_
# original_bytes is checked before writing - if it doesn't match, this
# aborts rather than overwrite something unexpected (same safety
# convention as mechanic_ap_key_item_opcode.py's own opcode check).
RUNE_PDM_ISO_OFFSET = 0x06783A00
S18_ISO_OFFSET = 0xb474c40

TEXT_PATCHES = [
    # "ダミー" (Shift-JIS, 6 bytes) -> "AP" (2 bytes + null terminator) -
    # table 0x17, entry 0 (the card-name table used by the chest-pickup
    # popup specifically, via GetUIText(0x17, ...) inside
    # ResolveDialogueMessageID). Comfortably shorter than the original -
    # no other bytes need to move.
    (
        RUNE_PDM_ISO_OFFSET + 0x11dab4,
        bytes.fromhex("835f837e815b"),
        b"AP\x00",
    ),
    # "You have found\nthe %s card!" -> "You have found\nan %s Item!" -
    # table 2, entry 3's own full template string. Replacing the whole
    # string in one patch (rather than two separate, position-dependent
    # sub-patches for "the"->"an" and "card"->"Item") since "an" is 1
    # byte shorter than "the" - editing it in isolation would shift
    # everything after it, including "Item", out of position. The new
    # string (26 bytes) is 1 byte shorter than the original (27 bytes),
    # so it fits safely within the same space with one byte to spare.
    (
        RUNE_PDM_ISO_OFFSET + 0xfe1b6,
        b"You have found\nthe %s card!",
        b"You have found\nan %s Item!\x00",
    ),

    # --- Group 8: s18.pds's "has Jewel of Alanjeh already been
    # obtained" check (opcode 135, argument 20 - key item index 19,
    # Jewel of Alanjeh, under the game's own 1-indexed key item ID
    # scheme confirmed via s20.pds/s21.pds cross-checking) always
    # acts as if the item is NOT obtained - swaps the argument to 31
    # instead of redirecting the opcode itself, avoiding spending
    # another custom opcode slot. Confirmed via GetKeyItemObtained's
    # own decompiled logic (main_dol.c) that ID 31 stays within the
    # same bitmask word every real key item (1-30) uses, with no
    # out-of-bounds risk, and is never set by any real item - so this
    # bit is always 0, making the check permanently read as "not
    # obtained" while still running genuine, unmodified vanilla logic
    # (no new opcode needed at all). ---
    (
        S18_ISO_OFFSET + 0x4d7a30,
        b"\x00\x00\x00\x14",
        b"\x00\x00\x00\x1f",
    ),

    # --- Group 10 (S10_CARD_POOL_FIX): level 10's two card-user
    # enemies (rune.pdm decks 0x10f and 0x11e) can now both be alive
    # at once (thanks to the Castle Gate Key opening independent of
    # defeating the first one) but their combined card-model buffer
    # slot requirements exceed the pool's own hard maximum of 10 -
    # confirmed via main_dol.c analysis (SelectCameraMode's own
    # allocation loop is capped at exactly 10 slots regardless of
    # cameraMode; GetOrAllocateCardModelBuffer is called once per
    # distinct card model actually loaded). Trimming the 0x10f deck
    # from 5 cards down to 3, removing both Lizardman (card_id=5) and
    # Carbuncle (card_id=36) - Lizardman-only removal (5->4 cards)
    # confirmed insufficient to prevent the crash on its own. Final
    # active deck: Dragon Knight, Dark Raven, Skeleton.
    #
    # Same record-swap approach as before: Lizardman's own full
    # 0x30-byte record swapped into the excluded index-4 slot,
    # Dragon Knight's own record moved into index 0. Carbuncle (index
    # 1) swapped with Dark Raven (index 3, the new last-active slot
    # once card_count drops to 3) - Dark Raven ends up at index 1
    # (stays active), Carbuncle ends up at index 3 (now excluded
    # alongside Lizardman at index 4). card_count dropped from 5
    # straight to 3 (not staged through 4) since both removals are
    # being applied together.
    (
        RUNE_PDM_ISO_OFFSET + 0xf5fcc,
        bytes.fromhex("0005003c00000000000005dc64000000838a8355815b8368837d83930000000000000000000000000000000000000000"),
        bytes.fromhex("004a002300000000000009c43200000083688389834f815b839300000000000000000000000000000000000000000000"),
    ),
    (
        RUNE_PDM_ISO_OFFSET + 0xf608c,
        bytes.fromhex("004a002300000000000009c43200000083688389834f815b839300000000000000000000000000000000000000000000"),
        bytes.fromhex("0005003c00000000000005dc64000000838a8355815b8368837d83930000000000000000000000000000000000000000"),
    ),
    (
        RUNE_PDM_ISO_OFFSET + 0xf5ffc,
        bytes.fromhex("002400b40000271000004e2032000000834a815b836f8393834e838b0000000000000000000000000000000000000000"),
        bytes.fromhex("003f003c00000fa0000019644600000083658389815b838c834383758393000000000000000000000000000000000000"),
    ),
    (
        RUNE_PDM_ISO_OFFSET + 0xf605c,
        bytes.fromhex("003f003c00000fa0000019644600000083658389815b838c834383758393000000000000000000000000000000000000"),
        bytes.fromhex("002400b40000271000004e2032000000834a815b836f8393834e838b0000000000000000000000000000000000000000"),
    ),
    (
        RUNE_PDM_ISO_OFFSET + 0xf5faa,
        b"\x05",
        b"\x03",
    ),

    # --- Group 11 (S04_CARD_POOL_FIX): level 4's own special-case
    # deck (rune.pdm entry[14], type_id 0x11e, selected via
    # main_dol.c's own entity-address hash when multiple copies of
    # this monster type are simultaneously active) trimmed from 5
    # cards to 4, removing Blood Bush (card_id=72). Blood Bush is
    # already the last card in this deck (index 4), so unlike the
    # Lizardman fix this needs no record swap - card_count alone
    # excludes it directly.
    (
        RUNE_PDM_ISO_OFFSET + 0xf676a,
        b"\x05",
        b"\x04",
    ),
]


def apply(patcher):
    for addr, new_instruction in PATCHES:
        patcher.patch_word(addr, new_instruction)

    for iso_offset, expected, new_bytes in TEXT_PATCHES:
        patcher.file.seek(iso_offset)
        original = patcher.file.read(len(expected))
        if original != expected:
            raise ValueError(
                f"Expected {expected!r} at rune.pdm (iso offset {hex(iso_offset)}), "
                f"found {original!r} instead. Aborting rather than overwrite something unexpected."
            )
        patcher.file.seek(iso_offset)
        patcher.file.write(new_bytes)