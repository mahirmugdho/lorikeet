"""The clay rope round each stuck-down note: closed, just outside the paper, at the play layer."""

import time

import numpy as np

from lorikeet.render.clay.rope import THICKNESS, rope
from lorikeet.render.pencil import NOTE_GAP

SQUARE = ((-50.0, -50.0), (50.0, -50.0), (50.0, 50.0), (-50.0, 50.0))


def test_the_rope_runs_just_outside_the_paper_all_the_way_round():
    mesh = rope(SQUARE)
    x, z = mesh.positions[:, 0], -mesh.positions[:, 2]

    outside = np.maximum(np.abs(x), np.abs(z)) - 50  # how far out of the square each vertex is
    assert outside.min() > NOTE_GAP - 1.5  # the paper stays clear
    assert outside.max() < NOTE_GAP + 3 * THICKNESS + 2  # but it hugs it
    # All the way round: every side of the square has rope beside it.
    for side in (x > 55, x < -55, z > 55, z < -55):
        assert side.sum() > 100


def test_the_rope_lies_at_the_play_layer():
    depth = rope(SQUARE).positions[:, 1]
    assert np.abs(depth).max() < 2.5 * THICKNESS


def test_the_rope_is_a_closed_tube_facing_out():
    mesh = rope(SQUARE, seed=3)
    triangles = mesh.triangles
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    forward = {tuple(e) for e in edges.tolist()}
    assert len(forward) == len(edges)
    assert all((b, a) in forward for a, b in forward)  # no holes, no seams
    assert np.allclose(np.linalg.norm(mesh.normals, axis=1), 1, atol=1e-4)


def test_a_rope_is_quick_enough_to_build_mid_game():
    started = time.perf_counter()
    rope(SQUARE)
    assert time.perf_counter() - started < 0.05
