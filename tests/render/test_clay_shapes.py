"""Clay figures are built from soft shapes blended together, then turned into smooth meshes."""

import numpy as np
import pytest

from lorikeet.render.clay.mesher import mesh_field
from lorikeet.render.clay.shapes import (
    Coil,
    Coin,
    Ellipsoid,
    RoundCone,
    Scaled,
    Slab,
    Torus,
    rotation,
    smooth_union,
)


def points(*xyz: tuple[float, float, float]) -> np.ndarray:
    return np.array(xyz, dtype=np.float32)


def test_a_round_ellipsoid_is_an_exact_sphere():
    ball = Ellipsoid(centre=(1, 2, 3), radii=(5, 5, 5))

    d = ball.distance(points((1, 2, 3), (6, 2, 3), (1, 2, 10), (1, -5, 3)))

    assert d == pytest.approx([-5, 0, 2, 2], abs=1e-5)


def test_an_ellipsoid_is_zero_on_its_surface_and_negative_inside():
    egg = Ellipsoid(centre=(0, 0, 0), radii=(4, 2, 1))

    on = egg.distance(points((4, 0, 0), (0, 2, 0), (0, 0, 1)))
    inside = egg.distance(points((1, 0.5, 0.2)))

    assert on == pytest.approx([0, 0, 0], abs=1e-5)
    assert inside[0] < 0


def test_rotation_turns_a_shape_about_its_centre():
    # A long ellipsoid along x, turned 90 degrees about z, lies along y.
    rod = Ellipsoid(centre=(0, 0, 0), radii=(4, 1, 1), turn=rotation(heading=90))

    d = rod.distance(points((0, 4, 0), (4, 0, 0)))

    assert d[0] == pytest.approx(0, abs=1e-5)
    assert d[1] > 2


def test_a_round_cone_is_a_ball_at_each_end_joined_smoothly():
    cone = RoundCone(start=(0, 0, 0), end=(10, 0, 0), start_radius=3, end_radius=1)

    d = cone.distance(points((-3, 0, 0), (11, 0, 0), (0, 0, 3), (5, 0, 0)))

    assert d[:3] == pytest.approx([0, 0, 0], abs=1e-4)
    assert d[3] < -1.5  # well inside, halfway along


def test_smooth_union_is_a_plain_union_far_from_the_join():
    a = np.array([0.0, 5.0], dtype=np.float32)
    b = np.array([5.0, 0.0], dtype=np.float32)

    assert smooth_union(a, b, radius=2) == pytest.approx([0, 0])


def test_smooth_union_fills_in_the_crease_where_shapes_meet():
    """Where two shapes are about equally near, the blend reaches further than either: that's
    the soft neck of clay pressed into clay."""
    a = np.array([1.0], dtype=np.float32)
    b = np.array([1.0], dtype=np.float32)

    blended = smooth_union(a, b, radius=2)

    assert blended[0] == pytest.approx(0.5)  # 1 - radius / 4
    assert smooth_union(a, b, radius=0)[0] == pytest.approx(1.0)


def test_a_meshed_ball_is_closed_smooth_and_round():
    ball = Ellipsoid(centre=(0, 0, 0), radii=(10, 10, 10))

    mesh = mesh_field(ball.distance, lower=(-12, -12, -12), upper=(12, 12, 12), step=0.5)

    radius = np.linalg.norm(mesh.positions, axis=1)
    assert radius == pytest.approx(10, abs=0.01)  # vertices sit on the true surface
    radial = mesh.positions / radius[:, None]
    assert np.einsum("ij,ij->i", mesh.normals, radial).min() > 0.9999  # normals are smooth
    assert _is_closed(mesh.triangles)
    assert _area(mesh) == pytest.approx(4 * np.pi * 100, rel=0.01)


def test_mesh_triangles_face_outward():
    """Back faces are culled, so a triangle wound the wrong way would be a hole."""
    ball = Ellipsoid(centre=(0, 0, 0), radii=(6, 4, 5))

    mesh = mesh_field(ball.distance, lower=(-8, -8, -8), upper=(8, 8, 8), step=0.5)

    a, b, c = (mesh.positions[mesh.triangles[:, i]] for i in range(3))
    facing = np.cross(b - a, c - a)
    centroid_normal = mesh.normals[mesh.triangles].sum(axis=1)
    assert (np.einsum("ij,ij->i", facing, centroid_normal) > 0).all()


def test_a_shape_too_small_for_the_grid_gives_an_empty_mesh():
    speck = Ellipsoid(centre=(0.25, 0.25, 0.25), radii=(0.01, 0.01, 0.01))

    mesh = mesh_field(speck.distance, lower=(-2, -2, -2), upper=(2, 2, 2), step=1)

    assert len(mesh.positions) == 0
    assert len(mesh.triangles) == 0


def _is_closed(triangles: np.ndarray) -> bool:
    """Every edge is shared by exactly two triangles, once in each direction."""
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    forward = {tuple(e) for e in edges.tolist()}
    return len(forward) == len(edges) and all((b, a) in forward for a, b in forward)


def _area(mesh) -> float:
    a, b, c = (mesh.positions[mesh.triangles[:, i]] for i in range(3))
    return float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2)


def test_a_torus_is_a_ring_round_its_axis():
    ring = Torus(centre=(0, 0, 0), ring=10, tube=2)

    d = ring.distance(points((12, 0, 0), (0, -8, 0), (10, 0, 2), (0, 0, 0)))

    assert d == pytest.approx([0, 0, 0, 8], abs=1e-5)


def test_scaling_never_overstates_the_distance():
    ball = Ellipsoid(centre=(0, 0, 0), radii=(5, 5, 5))
    flat = Scaled(ball, (1.0, 0.4, 1.0))

    d = flat.distance(points((5, 0, 0), (0, 2, 0), (0, 4, 0)))

    assert d[:2] == pytest.approx([0, 0], abs=1e-5)
    assert 0 < d[2] <= 2.0 + 1e-5  # truly 2 from the squashed surface


def test_a_slab_keeps_its_outline_and_rounds_its_edges_inside_it():
    box = ((0.0, 0.0), (100.0, 0.0), (100.0, -20.0), (0.0, -20.0))  # x, z: 20 tall
    slab = Slab(box, front=-10, back=10, round=4)

    # Points are (x, depth, z).
    d = slab.distance(points((50, 0, 0), (50, 0, -10), (50, -10, -10), (50, -10, 0), (0, 0, 0)))

    assert d[0] == pytest.approx(0, abs=1e-4)  # the top edge, mid-depth: on the outline
    assert d[1] == pytest.approx(-10, abs=1e-4)  # the very middle
    assert d[2] == pytest.approx(0, abs=1e-4)  # the front face
    assert d[3] == pytest.approx(4 * (2**0.5 - 1), abs=1e-3)  # the front top edge is rounded
    assert d[4] > 0  # and so are the ends


def test_a_coil_is_a_round_rope_bent_round_an_oval_deeper_in_front_than_behind():
    coil = Coil(centre=(0, 0, 0), across=20, front=12, back=6, tube=2)

    d = coil.distance(points((22, 0, 0), (0, -14, 0), (0, 8, 0), (20, 0, 2), (-18, 0, 0)))

    assert d == pytest.approx([0, 0, 0, 0, 0], abs=1e-4)  # side, front, back, top, inside
    assert coil.distance(points((0, 0, 0)))[0] > 3  # the middle is empty


def test_a_coin_is_flat_faced_with_a_rounded_rim():
    coin = Coin(centre=(0, 0, 0), radius=20, thickness=6, round=2)

    d = coin.distance(points((0, -3, 0), (20, 0, 0), (0, 0, 20), (0, -5, 0), (0, 0, 0)))

    assert d[:3] == pytest.approx([0, 0, 0], abs=1e-4)  # the front face, and the rim
    assert d[3] == pytest.approx(2, abs=1e-4)  # 2 in front of the face
    assert d[4] < 0
    corner = coin.distance(points((20, -3, 0)))[0]  # where a sharp edge would be
    assert corner == pytest.approx(2 * (2**0.5 - 1), abs=1e-3)  # rounded off
