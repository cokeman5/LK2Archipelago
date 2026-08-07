def apply(patcher):
    # UpdateRedFairyBehavior: disables the automatic red_fairies_count
    # increment (addi r0,r4,1 -> addi r0,r4,0) so the AP client controls it.
    patcher.patch_word(0x80077034, 0x38040000)
