import struct
import logging

logger = logging.getLogger(__name__)


def apply(patcher, cardback_gtx: bytes, entry_index: int = 62):
    iso_file = patcher.file

    # The signature confirmed at the original .TEX container location
    iso_tex_header_signature = b'\x00\x0c\x2d\xc0\x00\x00\x00\x41\x00\x00\x01\x20\x00\x00\x2a\x80'

    search_start = 0x41D0000
    iso_file.seek(search_start)
    chunk = iso_file.read(4096)
    header_pos = chunk.find(iso_tex_header_signature)

    if header_pos == -1:
        logger.error("Could not find the .TEX container signature.")
        return

    sp_tex_iso_offset = search_start + header_pos

    # 1. Locate the target entry in the offset table
    iso_file.seek(sp_tex_iso_offset + 0x08 + (entry_index * 4))
    entry_offset = struct.unpack('>I', iso_file.read(4))[0]
    next_offset = struct.unpack('>I', iso_file.read(4))[0]

    original_total_size = next_offset - entry_offset
    target_address = sp_tex_iso_offset + entry_offset

    # 2. SURGICAL STEP: Read the original entry's header (first 32 bytes)
    # This contains the format, width, height, and mipmap data the game expects.
    iso_file.seek(target_address)
    original_gtx_header = iso_file.read(32)

    # 3. PREPARE PAYLOAD: Use the new pixels but skip its own header
    # cardback_gtx is assumed to have its own 32-byte header we discard.
    new_pixel_data = cardback_gtx[32:]

    # Reconstruct the entry: Original Header + New Pixels
    final_patch = original_gtx_header + new_pixel_data

    # 4. STRICT SIZE ENFORCEMENT
    # We MUST stay within the original byte-count of this entry.
    if len(final_patch) > original_total_size:
        logger.warning("Patch too large; truncating to match original entry size.")
        final_patch = final_patch[:original_total_size]
    elif len(final_patch) < original_total_size:
        padding_needed = original_total_size - len(final_patch)
        final_patch += b'\x00' * padding_needed

    # 5. WRITE & VERIFY
    iso_file.seek(target_address)
    iso_file.write(final_patch)
    iso_file.flush()

    iso_file.seek(target_address)
    verification = iso_file.read(4)
    if verification == original_gtx_header[:4]:  # Should still start with 'GTX1'
        logger.info(f"SUCCESS: Surgical patch applied to Entry {entry_index} at {hex(target_address)}")
    else:
        logger.error("FAILURE: Write verification failed.")