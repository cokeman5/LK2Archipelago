"""
Randomizes the XP cost to duplicate a card.

Order of operations:
    0. mode off - values are left at their vanilla settings, but a
                  multiplier below still applies to them, so a player can
                  scale a stat without randomizing it.
    1. shuffle   - redeal the vanilla values among the cards, so the overall
                   distribution is unchanged and only the assignment moves.
                   Takes priority over minimum/maximum when enabled.
       randomize - otherwise, roll every value independently in
                   [minimum, maximum].
    2. multiply  - scale whatever came out of step 1 and floor it. Use 1 for
                   no scaling.

Cards with a vanilla cost of 0 cannot be copied and are left untouched.
"""

import logging
import random

from .stats_database import StatsDatabase, MODE_RANDOMIZE, MODE_SHUFFLE

logger = logging.getLogger(__name__)

FIELD = "copy_exp_cost"


def apply(patcher, output_data, minimum, maximum, mode, multiplier):
    rng = random.Random(output_data.get("Seed", -1) + 5)
    db = StatsDatabase(patcher)
    slots = db.slots(FIELD, skip_zero=True)

    if mode == MODE_SHUFFLE:
        results = db.shuffle_field(FIELD, rng, slots=slots)
        how = "shuffled"
    elif mode == MODE_RANDOMIZE:
        results = db.randomize_field(FIELD, minimum, maximum, rng, slots=slots)
        how = f"randomized to {minimum}..{maximum}"
    else:
        # Mode off, but a multiplier can still scale the vanilla values -
        # that is the whole reason this branch exists rather than returning.
        results = {}
        how = "left vanilla"

    if multiplier != 1:
        results = db.scale_field(FIELD, multiplier, slots=slots)
        how += f", then x{multiplier}"

    if not results:
        logger.info(f"[{FIELD}] nothing to do (mode off, multiplier 1)")
        return

    logger.info(f"[copy_exp_cost] {how} across {len(results)} value(s)")
    for (card_id, index), value in sorted(results.items(),
                                          key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        where = "" if index is None else f"[{index}]"
        logger.debug(f"[copy_exp_cost] card {card_id}{where} "
                     f"({db.read_string(card_id, 'name_jp')}) = {value}")