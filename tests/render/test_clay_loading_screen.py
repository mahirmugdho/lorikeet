"""The loading screen shows its pre-rendered clay pictures, and fills its track with beads."""

from importlib.resources import files

import pygame
import pytest
from panda3d.core import NodePath

from lorikeet.render.clay.loading_art import BEADS
from lorikeet.render.clay.loading_screen import LoadingScreen

ART = files("lorikeet.render.clay").joinpath("art")


@pytest.mark.parametrize(
    "name", ["loading_words", "loading_track", "loading_bead_0", "loading_bead_1", "loading_bead_2"]
)
def test_each_picture_is_there_with_a_clear_background(name: str):
    image = pygame.image.load(str(ART.joinpath(f"{name}.png")))
    assert image.get_alpha() is not None or image.get_flags() & pygame.SRCALPHA
    corner = image.get_at((0, 0))
    assert corner.a == 0  # clear round the clay


def visible_beads(root: NodePath) -> int:
    cards = root.find("loading screen").getChildren()
    return sum(
        1 for card in cards if card.getName().startswith("loading_bead") and not card.isHidden()
    )


def test_the_screen_is_hidden_until_shown_then_shows_as_many_beads_as_asked():
    root = NodePath("canvas 2d")
    screen = LoadingScreen(root, (1920, 1080))

    assert root.find("loading screen").isHidden()
    screen.show(True, beads=5, frame=0)
    assert not root.find("loading screen").isHidden()
    assert visible_beads(root) == 5
    screen.show(True, beads=BEADS, frame=1)
    assert visible_beads(root) == BEADS
    screen.show(False, beads=BEADS, frame=2)
    assert root.find("loading screen").isHidden()


def test_a_bead_pops_in_a_little_big_then_settles():
    root = NodePath("canvas 2d")
    screen = LoadingScreen(root, (1920, 1080))
    bead = next(
        c
        for c in root.find("loading screen").getChildren()
        if c.getName().startswith("loading_bead")
    )

    screen.show(True, beads=1, frame=0)
    arriving = bead.getSx()
    screen.show(True, beads=1, frame=1)
    assert arriving > bead.getSx()
