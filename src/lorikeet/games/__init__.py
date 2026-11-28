"""Lorikeet's games.

A game imports nothing of Lorikeet's but `lorikeet.interface` (the scenes it's given) and
`lorikeet.view` (how it describes what it shows), so it runs with any input, renderer and
output (ADR 0004, ADR 0008). `tests/test_boundaries.py` checks that.
"""
