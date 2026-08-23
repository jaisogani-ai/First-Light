"""Shared constants. Kept in one place so no value drifts out of sync across modules."""

# The sequence counter's starting point for a stream with no prior accepted commands.
# Arbitrary but documented — earlier revisions of this codebase used an unexplained 1042
# here (a leftover from the original hackathon prototype's fake verifier, which hardcoded
# `sequence_no > 1042` as its entire "replay protection"). The actual value doesn't matter
# for correctness (any fixed genesis works since the real protection is the strictly-
# increasing DB-backed check in backend/verifier.py), but it should be a plain, obviously
# arbitrary number rather than one that looks like it might be load-bearing.
INITIAL_SEQUENCE_NO = 1000
