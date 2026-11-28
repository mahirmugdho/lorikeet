"""Figures are built in other processes, so a first build never stalls a frame."""

import time

from lorikeet.render.clay.builder import Builder
from lorikeet.render.clay.figure import Figure, Piece
from lorikeet.render.clay.shapes import Ellipsoid


def ball() -> Figure:
    return Figure((Piece(Ellipsoid((0, 0, 0), (5, 5, 5)), "c"),), {"c": (90, 90, 90)})


def test_a_figure_is_not_ready_at_once_then_arrives(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the workers' disk cache goes here, not in the repo
    builder = Builder(workers=1)
    try:
        assert builder.mesh("ball", ball, 1.0) is None  # asked for: building, not waited for
        deadline = time.monotonic() + 60
        mesh = None
        while mesh is None and time.monotonic() < deadline:
            time.sleep(0.05)
            mesh = builder.mesh("ball", ball, 1.0)
        assert mesh is not None
        assert len(mesh.triangles) > 0
    finally:
        builder.close()
