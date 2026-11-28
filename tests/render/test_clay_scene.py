"""The clay set follows the game's View: things appear, move, pose and go, with no GPU.

CI has no display or GL, but Panda3D's scene graph doesn't need one: a stand-in for
ShowBase with a plain scene root is enough to build the stage and check where everything
is put. The real figures take seconds to build, so tiny balls stand in for them.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from panda3d.core import Camera, Mat4, NodePath

import lorikeet.render.clay.scene as scene_module
from lorikeet.render.clay.bed import FLOWERS
from lorikeet.render.clay.builder import BuildNow
from lorikeet.render.clay.coords import to_world
from lorikeet.render.clay.detail import clay_detail
from lorikeet.render.clay.figure import Figure, Piece, build
from lorikeet.render.clay.scene import LAYER_DEPTH, ClayScene, Look
from lorikeet.render.clay.shapes import Ellipsoid
from lorikeet.render.clay.stage import SEEN, Light, Stage
from lorikeet.view import Circle, Outline, Text, Thing, View


def ball(thing: Thing) -> Figure:
    return Figure((Piece(Ellipsoid((0, 0, 0), (3, 3, 3)), "c"),), {"c": (90, 90, 90)})


QUICK = BuildNow(lambda figure, step: build(figure, 1.0))  # coarse, and no disk cache


def stage() -> Stage:
    base = SimpleNamespace(
        render=NodePath("render"), render2d=NodePath("render2d"), cam=NodePath(Camera("cam"))
    )
    return Stage(base, (320, 180), clay_detail(size=32), Light())


@pytest.fixture
def clay(monkeypatch) -> ClayScene:
    monkeypatch.setattr(
        scene_module,
        "LOOKS",
        {
            "bird": Look(ball, step=1.0, boil=0.6, jitter=1.0),
            "terrain": Look(ball, step=1.0, boil=0.2, jitter=0.0),
        },
    )
    return ClayScene(stage(), QUICK)


def placed(clay: ClayScene, name: str) -> NodePath:
    found = clay.stage.root.find(f"**/{name}")
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


def test_a_note_casts_a_shadow_and_gets_a_rope_round_it_but_no_figure(clay):
    note = Thing(100_001, "note", Outline(((-50, -50), (50, -50), (50, 50), (-50, 50))), (200, 90))
    clay.show(View((note,)), now=0.0)

    box = placed(clay, "note shadow")
    assert box.isHidden(SEEN)  # the camera never draws the paper's stand-in
    assert not box.isHidden()  # but the light does
    outline = placed(clay, "note rope")
    assert not outline.isHidden(SEEN)  # the rope round it is seen
    assert tuple(placed(clay, "note 100001").getPos()) == pytest.approx(to_world((200, 90)))


def test_the_go_ring_is_pressed_onto_the_backdrop(clay, monkeypatch):
    monkeypatch.setitem(
        scene_module.LOOKS, "go", Look(ball, step=1.0, boil=0.3, jitter=0.0, depth=37.0)
    )
    clay.show(View((Thing(2, "go", Circle(70), (130, 920)),)), now=0.0)

    assert placed(clay, "go 2").getPos()[1] == pytest.approx(37.0)


def test_things_that_leave_the_view_leave_the_set(clay):
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")
    clay.show(View((lori,)), now=0.0)
    clay.show(View(()), now=0.1)

    assert clay.stage.root.find("**/bird 4").isEmpty()


def test_kinds_without_a_clay_look_are_left_out(clay):
    words = Thing(5, "message", Circle(10), (10, 10))
    clay.show(View((words,)), now=0.0)

    assert clay.stage.root.find("**/message 5").isEmpty()


class Slow:
    """A builder whose figures take two frames to be ready."""

    def __init__(self) -> None:
        self.asked: dict[object, int] = {}

    def mesh(self, key, figure, step):
        self.asked[key] = self.asked.get(key, 0) + 1
        return build(figure(), 1.0) if self.asked[key] > 2 else None


def test_a_thing_joins_the_set_once_its_figure_is_built(clay):
    clay.builder = Slow()
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")

    clay.show(View((lori,)), now=0.0)
    clay.show(View((lori,)), now=0.02)
    assert clay.stage.root.find("**/bird 4").isEmpty()  # not ready: left out, no stall

    clay.show(View((lori,)), now=0.04)
    placed(clay, "bird 4")


def test_newly_built_figures_can_join_one_a_frame(clay):
    clay._new_per_frame = 1
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")
    ledge = Thing(100, "terrain", Outline(((-20, -5), (20, -5), (20, 5), (-20, 5))), (60, 150))

    clay.show(View((lori, ledge)), now=0.0)
    assert clay.stage.root.find("**/terrain 100").isEmpty()  # the second waits a frame
    clay.show(View((lori, ledge)), now=0.02)
    placed(clay, "bird 4")
    placed(clay, "terrain 100")


def tall(thing: Thing) -> Figure:
    """An upright, egg-like stand-in: taller than it's wide."""
    return Figure((Piece(Ellipsoid((0, 0, 0), (3, 3, 5)), "c"),), {"c": (200, 200, 200)})


def test_the_egg_rests_on_its_lowest_point_however_it_has_rolled(clay, monkeypatch):
    monkeypatch.setitem(scene_module.LOOKS, "egg", Look(tall, step=1.0, boil=0.3, jitter=0.0))
    ground = to_world((100, 85))[2]  # the bottom of its ball, radius 5 at y 80
    for angle in (0.0, 0.5, 1.5708, 2.2):
        egg = Thing(1000, "egg", Circle(5), (100, 80), angle=angle, layer=3)
        clay.show(View((egg,)), now=0.0)

        low, _ = placed(clay, "egg 1000").getTightBounds(clay.stage.root)
        assert low.z == pytest.approx(ground, abs=0.05)


def test_the_go_disc_gives_a_little_as_the_go_note_goes_on(clay, monkeypatch):
    monkeypatch.setitem(scene_module.LOOKS, "go", Look(ball, step=1.0, boil=0.3, jitter=0.0))
    sizes = []
    for frame, pose_name in enumerate(("off", "off", "on", "on", "on", "on")):
        go = Thing(2, "go", Circle(70), (130, 920), pose=pose_name)
        clay.show(View((go,)), now=frame / 12 + 0.001)
        sizes.append(round(placed(clay, "go 2").getScale()[0], 3))

    assert sizes[:2] == [1.0, 1.0]
    assert sizes[2] < 1.0 < sizes[3]  # gives, springs back...
    assert sizes[4:] == [1.0, 1.0]  # ...and settles


def test_the_flower_bed_waits_with_its_buds_hidden_then_blooms(clay, monkeypatch):
    monkeypatch.setitem(scene_module.LOOKS, "blossom", Look(ball, step=1.0, boil=0.3, jitter=0.0))
    bed = Thing(1, "blossom", Circle(20), (300, 100), layer=1)
    clay.show(View((bed,)), now=0.0)

    flowers = [placed(clay, f"flower {i}") for i in range(len(FLOWERS))]
    for flower, node in zip(FLOWERS, flowers, strict=True):
        assert node.isHidden() == flower.bud

    won = Thing(1, "blossom", Circle(20), (300, 100), layer=1, pose="won")
    clay.show(View((won,)), now=1.0)
    clay.show(View((won,)), now=6.0)
    for node in flowers:
        assert not node.isHidden()
        shown = [
            i for i, piece in enumerate(node.find("head").getChildren()) if not piece.isHidden()
        ]
        assert shown == [3]  # wide open


def test_a_broken_egg_splats_flat_for_a_frame_then_lies_in_pieces(clay, monkeypatch):
    monkeypatch.setitem(scene_module.LOOKS, "egg", Look(tall, step=1.0, boil=0.3, jitter=0.0))
    monkeypatch.setattr(scene_module, "BROKEN_EGG", Look(ball, step=1.0, boil=0.3, jitter=0.0))
    rolling = Thing(1000, "egg", Circle(5), (100, 80), angle=1.0, layer=3)
    clay.show(View((rolling,)), now=0.001)
    broken = Thing(1000, "egg", Circle(5), (100, 80), angle=1.0, layer=3, pose="broken")

    clay.show(View((broken,)), now=1 / 12 + 0.001)  # the frame it hits the floor
    splat = placed(clay, "egg 1000")
    assert splat.getSz() < 1 < splat.getSx()  # flattened, wider

    clay.show(View((broken,)), now=2 / 12 + 0.001)  # the next frame: in pieces
    pieces = placed(clay, "egg 1000")
    assert (pieces.getSx(), pieces.getSz()) == pytest.approx((1.0, 1.0))
    assert pieces.getR() == pytest.approx(0.0)  # lying upright, however it rolled
    lid, pool = placed(clay, "top half"), placed(clay, "puddle")
    assert lid.getMat().almostEqual(Mat4.identMat())  # first the crack shows...
    assert pool.isHidden()

    clay.show(View((broken,)), now=10 / 12 + 0.001)  # later
    assert lid.getX() > 2  # ...then the top half has tipped over to the right
    assert not pool.isHidden()  # and the puddle has spread


def test_the_set_counts_what_is_still_being_built(clay):
    clay.builder = Slow()
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")

    clay.show(View((lori,)), now=0.0)
    assert clay.missing == 1
    clay.show(View((lori,)), now=0.02)
    clay.show(View((lori,)), now=0.04)
    assert clay.missing == 0


def test_holding_hides_every_thing_but_not_the_backdrop(clay):
    lori = Thing(4, "bird", Circle(34), (100, 80), pose="idle")
    clay.show(View((lori,)), now=0.0)

    clay.hold(True)
    assert placed(clay, "bird 4").isHidden()
    assert not clay.stage.backdrop.isHidden()
    clay.hold(False)
    assert not placed(clay, "bird 4").isHidden()


def test_words_are_written_in_clay_letters_on_the_backdrop_centred_where_the_view_says(clay):
    words = Thing(6, "hint", Text("Go on!", 40), (160, 30), layer=4)
    clay.show(View((words,)), now=0.0)

    place = placed(clay, "hint 6")
    letters = place.getChildren()
    assert len(letters) == 5  # "Go on!" without its space
    x, depth, z = place.getPos()
    assert (x, z) == pytest.approx((160, -30))
    assert depth > 30  # back against the backdrop
    across = [letter.getX() for letter in letters]
    assert across == sorted(across)  # left to right
    assert (across[0] + across[-1]) / 2 == pytest.approx(0, abs=12)  # about centred


def test_progress_is_the_share_of_needed_figures_that_are_built(clay):
    clay.builder = Slow()
    things = (Thing(4, "bird", Circle(34), (100, 80)), Thing(5, "bird", Circle(20), (200, 80)))

    clay.show(View(things), now=0.0)
    assert clay.progress() == 0.0
    clay.show(View(things), now=0.02)
    clay.show(View(things), now=0.04)
    assert clay.progress() == 1.0
