"""
Randomizes level background music by shuffling audio stream filenames
in place - relies on a 1:1 mapping between levels and music and on
every shuffled filename being exactly the same length, since this
only ever renames files, never resizes the region.

Audio stream files starting with "m" are level background music - the
2 digits after "m" are the level ID, the last digit is 0 for normal
background music and non-zero for a cutscene variant. Files starting
with "p" are voice lines and are never shuffled. STREAMS_TO_SHUFFLE
also includes a few non-level streams (Battle, Lasbos, VSMenu) that
can be shuffled in with the rest.

Fixes 2 real bugs found in the original implementation this was based
on:
1. Any stream whose name matched a shuffle-target prefix but whose
   suffix was neither exactly "L.dsp" nor "R.dsp" was silently
   dropped from the rebuilt name list entirely (no error), which
   would leave the region's own overall byte length wrong on write.
   Here, that case raises loudly instead.
2. Stereo L/R pairing was done by peeking the last shuffled name for
   "L.dsp" then popping it for "R.dsp" immediately after - correct
   only if the ISO's own name table strictly alternates L-then-R for
   every stream with zero interleaving. Here, each base stream name is
   paired with its own single shuffled replacement explicitly by name,
   with no assumption about ordering between different streams' own L
   and R entries.
"""

import random

STREAMS_TO_SHUFFLE = [
    b"m010", b"m020", b"m030", b"m040", b"m050", b"m060", b"m070", b"m080", b"m090", b"m100",
    b"m110", b"m120", b"m130", b"m140", b"m150", b"m160", b"m170", b"m180", b"m190", b"m200",
    b"m210", b"m220", b"m230", b"m240", b"m250", b"m260", b"m270", b"m400", b"m410", b"m420",
    b"m750", b"m900", b"m910", b"m920", b"m930", b"m940", b"m950",
]

START_ADDRESS = 0x00195F20
END_ADDRESS = 0x0019709C


def apply(patcher, output_data):
    random.seed(output_data.get("Seed", -1))
    shuffled_streams = random.sample(STREAMS_TO_SHUFFLE, len(STREAMS_TO_SHUFFLE))
    replacement_for = dict(zip(STREAMS_TO_SHUFFLE, shuffled_streams))

    length = END_ADDRESS - START_ADDRESS
    patcher.file.seek(START_ADDRESS)
    original_region = patcher.file.read(length)
    stream_name_byte_strings = original_region.split(b"\x00")

    new_stream_name_byte_strings = []
    for name_bytes in stream_name_byte_strings:
        prefix, suffix = name_bytes[:4], name_bytes[4:]
        if prefix not in STREAMS_TO_SHUFFLE:
            new_stream_name_byte_strings.append(name_bytes)
            continue
        if suffix not in (b"L.dsp", b"R.dsp"):
            raise ValueError(
                f"Stream name {name_bytes!r} matched shuffle-target prefix {prefix!r} "
                f"but its own suffix isn't exactly 'L.dsp' or 'R.dsp' - aborting rather "
                f"than silently drop it and corrupt this region's own length."
            )
        new_stream_name_byte_strings.append(replacement_for[prefix] + suffix)

    new_region = b"\x00".join(new_stream_name_byte_strings)
    if len(new_region) != length:
        raise ValueError(
            f"Rebuilt audio stream region is {len(new_region)} bytes, expected exactly "
            f"{length} bytes (every shuffled name must be the same length as the "
            f"original it replaced) - aborting rather than write a misaligned region."
        )

    patcher.file.seek(START_ADDRESS)
    patcher.file.write(new_region)
