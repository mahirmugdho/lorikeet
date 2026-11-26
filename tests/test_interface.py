"""The contract games see: pieces, scenes, and the placed/removed diff (ADR 0004)."""

import dataclasses

import pytest

from lorikeet.interface import (
    Changes,
    FakeSceneSource,
    Piece,
    PieceState,
    Point,
    Polygon,
    Scene,
    SceneSource,
    changes,
    square,
)

MOVING, SETTLED, HIDDEN = PieceState.MOVING, PieceState.SETTLED, PieceState.HIDDEN

# An L of three unit squares: concave, so it needs two convex parts.
L_OUTLINE: Polygon = ((0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2))
L_PARTS: tuple[Polygon, ...] = (((0, 0), (2, 0), (2, 1), (0, 1)), ((0, 1), (1, 1), (1, 2), (0, 2)))


def piece(id: int, state: PieceState = SETTLED, center: Point = (100, 100)) -> Piece:
    outline = square(center, 50)
    return Piece(id=id, color="blue", state=state, outline=outline, parts=(outline,))


def test_square_lists_corners_clockwise_from_top_left():
    assert square((10, 20), 4) == ((8, 18), (12, 18), (12, 22), (8, 22))


# Piece


def test_center_of_a_square_is_its_middle():
    assert piece(1, center=(300, 200)).center == pytest.approx((300, 200))


def test_center_is_the_area_centroid_not_the_average_corner():
    # The corners average to (1, 1); the L's balance point is pulled toward its filled corner.
    l_piece = Piece(id=1, color="blue", state=SETTLED, outline=L_OUTLINE, parts=L_PARTS)

    assert l_piece.center == pytest.approx((5 / 6, 5 / 6))


def test_piece_cannot_be_changed_after_creation():
    with pytest.raises(dataclasses.FrozenInstanceError):
        piece(1).state = HIDDEN  # pyright: ignore[reportAttributeAccessIssue]


def test_concave_outline_is_allowed():
    Piece(id=1, color="blue", state=SETTLED, outline=L_OUTLINE, parts=L_PARTS)


def test_outline_needs_three_points():
    with pytest.raises(ValueError, match="at least 3 points"):
        Piece(id=1, color="blue", state=SETTLED, outline=((0, 0), (1, 1)), parts=L_PARTS)


def test_outline_needs_an_area():
    in_a_line: Polygon = ((0, 0), (1, 1), (2, 2))

    with pytest.raises(ValueError, match="no area"):
        Piece(id=1, color="blue", state=SETTLED, outline=in_a_line, parts=L_PARTS)


def test_piece_needs_at_least_one_part():
    with pytest.raises(ValueError, match="at least one part"):
        Piece(id=1, color="blue", state=SETTLED, outline=L_OUTLINE, parts=())


def test_parts_must_be_convex():
    with pytest.raises(ValueError, match="convex"):
        Piece(id=1, color="blue", state=SETTLED, outline=L_OUTLINE, parts=(L_OUTLINE,))


# Scene


def test_scene_starts_with_no_pieces():
    assert Scene(time=0.0).pieces == ()


def test_scene_rejects_two_pieces_with_the_same_id():
    with pytest.raises(ValueError, match="unique"):
        Scene(time=0.0, pieces=(piece(7), piece(7, center=(400, 400))))


# changes(): a piece counts as placed while it's SETTLED or HIDDEN.


def test_piece_that_settles_is_placed():
    settled = piece(1, SETTLED)

    found = changes(Scene(0.0, (piece(1, MOVING),)), Scene(1.0, (settled,)))

    assert found == Changes(placed=(settled,), removed=())


def test_piece_that_appears_already_settled_is_placed():
    # A game that skipped frames never saw it MOVING.
    settled = piece(1, SETTLED)

    assert changes(Scene(0.0), Scene(1.0, (settled,))).placed == (settled,)


def test_moving_piece_is_not_placed():
    assert changes(Scene(0.0), Scene(1.0, (piece(1, MOVING),))) == Changes()


def test_hand_covering_a_piece_changes_nothing():
    assert changes(Scene(0.0, (piece(1, SETTLED),)), Scene(1.0, (piece(1, HIDDEN),))) == Changes()


def test_piece_coming_back_into_view_is_not_placed_again():
    assert changes(Scene(0.0, (piece(1, HIDDEN),)), Scene(1.0, (piece(1, SETTLED),))) == Changes()


def test_hidden_piece_that_is_gone_is_removed_as_it_last_looked():
    hidden = piece(1, HIDDEN)

    assert changes(Scene(0.0, (hidden,)), Scene(3.0)) == Changes(placed=(), removed=(hidden,))


def test_moving_piece_that_vanishes_was_never_placed_so_is_not_removed():
    assert changes(Scene(0.0, (piece(1, MOVING),)), Scene(1.0)) == Changes()


def test_merging_two_pieces_removes_both_and_places_the_bigger_one():
    left, right = piece(1, center=(100, 100)), piece(2, center=(150, 100))
    merged = Piece(
        id=3,
        color="blue",
        state=SETTLED,
        outline=((75, 75), (175, 75), (175, 125), (75, 125)),
        parts=(((75, 75), (175, 75), (175, 125), (75, 125)),),
    )

    found = changes(Scene(0.0, (left, right)), Scene(1.0, (merged,)))

    assert found == Changes(placed=(merged,), removed=(left, right))


# FakeSceneSource


def test_fake_source_is_a_scene_source():
    source: SceneSource = FakeSceneSource([])  # pyright checks the protocol here

    assert source.latest() == Scene(time=0.0)


def test_fake_source_plays_scenes_in_order_then_repeats_the_last():
    first, second = Scene(0.0), Scene(1.0, (piece(1),))
    source = FakeSceneSource([first, second])

    assert [source.latest() for _ in range(4)] == [first, second, second, second]
