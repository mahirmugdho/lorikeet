"""Where the sim's palette sits: one swatch per colour, in a row along the bottom."""

from lorikeet.sim.palette import Palette

# Three 60 px swatches with 20 px gaps are 220 px wide: centred on a 1000 px canvas, they
# start at x=390. Their centres sit 20 + 30 px above the bottom edge.
PALETTE = Palette(
    ("yellow", "pink", "green"), canvas_size=(1000, 600), swatch=60, gap=20, margin=20
)


def test_swatches_sit_in_a_row_centred_along_the_bottom():
    assert PALETTE.swatches() == [
        ("yellow", (420, 550)),
        ("pink", (500, 550)),
        ("green", (580, 550)),
    ]


def test_swatch_at_finds_the_colour_under_a_point():
    assert PALETTE.swatch_at((505, 560)) == "pink"


def test_swatch_at_is_none_between_swatches():
    assert PALETTE.swatch_at((460, 550)) is None


def test_the_bar_covers_the_gaps_between_swatches():
    assert PALETTE.covers((460, 550))


def test_the_bar_leaves_the_playfield_above_it_alone():
    assert not PALETTE.covers((500, 300))
