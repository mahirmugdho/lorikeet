"""The clay set follows the game's View: things appear, move, pose and go, with no GPU.

CI has no display or GL, but Panda3D's scene graph doesn't need one: a stand-in for
ShowBase with a plain scene root is enough to build the stage and check where everything
is put. The real figures take seconds to build, so tiny balls stand in for them.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from panda3d.core import Camera, NodePath

import lorikeet.render.clay.scene as scene_module
from lorikeet.render.clay.coords import to_world
from lorikeet.render.clay.detail import clay_detail
from lorikeet.render.clay.figure import Figure, Piece, build
from lorikeet.render.clay.scene import LAYER_DEPTH, ClayScene, Look
from lorikeet.render.clay.shapes import Ellipsoid
from lorikeet.render.clay.stage import SEEN, Light, Stage
from lorikeet.view import Circle, Outline, Thing, View


def ball(thing: Thing) -> Figure:
    return Figure((Piece(Ellipsoid((0, 0, 0), (3, 3, 3)), "c"),), {"c": (90, 90, 90)})


@pytest.fixture
def clay(monkeypatch) -> ClayScene:
    monkeypatch.setattr(scene_module, "built", lambda f, step: build(f, 1.0))  # no disk cache
    monkeypatch.setattr(
        scene_module,
        "LOOKS",
        {
            "bird": Look(ball, step=1.0, boil=0.6, jitter=1.0),
            "terrain": Look(ball, step=1.0, boil=0.2, jitter=0.0),
        },
    )
    base = SimpleNamespace(
        render=NodePath("render"), render2d=NodePath("render2d"), cam=NodePath(Camera("cam"))
    )
    return ClayScene(Stage(base, (320, 180), clay_detail(size=32), Light()))


def placed(clay: ClayScene, name: str) -> NodePath:
    found = clay.stage.root.find(name)
    assert not found.isEmpty(), name
    return found


def test_a_thing_lands_where_the_view_puts_it_at_its_layers_depth(clay):
    ledge = Thing(100, "terrain", Outline(((-20, -5), (20, -5), (20, 5), (-20, 5))), (60, 150))
    clay.show(View((ledge,)), now=0.0)

    node = placed(clay, "terrain 100")
    assert tuple(node.getPos()) == pytest.approx(to_world((60, 150), 0.0))  # ground: no jitter


def test_figures_jitter_a_little_and_hold_it_for_a_stop_motion_frame(clay):
    lori = Thing(4, "bird", Circle(34), (100, 80), layer=2, pose="idle")
    positions = []
    for now in (0.0, 0.04, 0.09):  # the first two are one 12 fps frame, the last the next
        clay.show(View((lori,)), now)
        positions.append(tuple(placed(clay, "bird 4").getPos()))

    home = np.array(to_world((100, 80), -2 * LAYER_DEPTH))
    assert np.abs(np.array(positions) - home).max() <= 0.4 + 1e-6
    assert positions[0] == positions[1]
    assert positions[1] != positions[2]


def test_notes_only_cast_shadows(clay):
    note = Thing(100_001, "note", Outline(((-50, -50), (50, -50), (50, 50), (-50, 50))), (200, 90))
    clay.show(View((note,)), now=0.0)

    box = placed(clay, "note shadow")
    assert box.isHidden(SEEN)  # the camera never draws it
    assert not box.isHidden()  # but the light does


def test_things_that_leave_the_view_leave_the_set(clay):
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")
    clay.show(View((lori,)), now=0.0)
    clay.show(View(()), now=0.1)

    assert clay.stage.root.find("bird 4").isEmpty()


def test_kinds_without_a_clay_look_are_left_out(clay):
    words = Thing(5, "message", Circle(10), (10, 10))
    clay.show(View((words,)), now=0.0)

    assert clay.stage.root.find("message 5").isEmpty()
