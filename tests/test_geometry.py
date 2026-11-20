import numpy as np
import pytest

from lorikeet.geometry import apply_homography, homography_from_corners

# A 1280x720 projector frame, as the webcam sees it from off to one side: a skewed quad.
PROJECTOR = [(0, 0), (1280, 0), (1280, 720), (0, 720)]
CAMERA = [(212, 148), (1043, 101), (1101, 655), (180, 590)]


def _diagonal_intersection(quad: list[tuple[int, int]]) -> tuple[float, float]:
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = quad
    # Line through corners 0 and 2, intersected with the line through corners 1 and 3.
    denom = (x1 - x3) * (y2 - y4) - (y1 - y3) * (x2 - x4)
    t = ((x1 - x2) * (y2 - y4) - (y1 - y2) * (x2 - x4)) / denom
    return (x1 + t * (x3 - x1), y1 + t * (y3 - y1))


def test_camera_corners_map_onto_projector_corners():
    h = homography_from_corners(CAMERA, PROJECTOR)

    np.testing.assert_allclose(apply_homography(h, CAMERA), PROJECTOR, atol=1e-6)


def test_centre_of_the_camera_quad_lands_on_the_projector_centre():
    # Homographies preserve straight lines, so where the camera quad's diagonals cross
    # must map to where the projector frame's diagonals cross: its exact centre.
    h = homography_from_corners(CAMERA, PROJECTOR)

    centre = apply_homography(h, [_diagonal_intersection(CAMERA)])

    np.testing.assert_allclose(centre, [(640, 360)], atol=1e-6)


def test_perspective_divide_is_applied():
    h = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.001, 0.0, 1.0]])

    # w = 0.001 * 1000 + 1 = 2, so (1000, 500) must come out halved.
    np.testing.assert_allclose(apply_homography(h, [(1000, 500)]), [(500, 250)])


def test_collinear_corners_are_rejected():
    with pytest.raises(ValueError, match="collinear"):
        homography_from_corners([(0, 0), (1, 1), (2, 2), (0, 5)], PROJECTOR)


def test_needs_exactly_four_corners():
    with pytest.raises(ValueError, match="exactly 4"):
        homography_from_corners(CAMERA[:3], PROJECTOR[:3])
