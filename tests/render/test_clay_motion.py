"""Stop-motion: poses and jitter step 12 times a second; Lori's poses squash, hop and flap."""

import numpy as np
import pytest

from lorikeet.render.clay.lori import FEET, NECK
from lorikeet.render.clay.motion import (
    FPS,
    Animator,
    BirdPose,
    bird_parts,
    bird_pose,
    frame_of,
    jitter,
)


def test_stop_motion_time_holds_each_frame_for_a_twelfth_of_a_second():
    assert FPS == 12
    assert frame_of(0.0) == frame_of(0.08) == 0
    assert frame_of(1 / 12 + 1e-6) == 1
    assert frame_of(1.0) == 12


def test_jitter_is_small_the_same_within_a_frame_and_new_each_frame():
    """The animator never puts a model back in exactly the same place."""
    a, same, nxt = jitter(4, 10), jitter(4, 10), jitter(4, 11)

    assert a == same
    assert a != nxt
    for frame in range(200):
        j = jitter(4, frame)
        assert abs(j.dx) <= 0.5 and abs(j.dy) <= 0.5
        assert abs(j.turn) <= 0.5  # degrees
        assert abs(j.scale - 1) <= 0.006


def test_idle_breathes_gently_around_the_rest_pose():
    poses = [bird_pose("idle", t / 12) for t in range(60)]
    assert all(0.97 < p.squash < 1.03 for p in poses)
    assert all(p.hop == 0 for p in poses)


def test_laying_squats_and_happy_hops():
    assert bird_pose("laying", 1.0).squash < 0.95
    hops = [bird_pose("happy", t / 12).hop for t in range(24)]
    assert max(hops) > 10
    assert min(hops) == 0  # back on her feet between hops


def test_an_unknown_pose_is_the_idle_one():
    assert bird_pose("dancing", 0.5) == bird_pose("idle", 0.5)


def test_a_new_pose_takes_over_over_a_few_frames_not_at_once():
    animator = Animator()
    animator.pose(4, "idle", now=0.0)
    animator.pose(4, "laying", now=1.0)  # the game changes the pose

    first = animator.pose(4, "laying", now=1.0)  # the frame it changed: still the old pose
    later = animator.pose(4, "laying", now=1.5)  # six frames on: all the new one

    assert first == bird_pose("idle", 1.0)
    assert later == bird_pose("laying", 0.5)


def test_poses_only_change_on_stop_motion_frames():
    animator = Animator()
    a = animator.pose(4, "happy", now=0.30)
    b = animator.pose(4, "happy", now=0.33)  # same 12 fps frame
    assert a == b


def test_turning_the_head_keeps_the_neck_where_it_is():
    neck = np.array([*NECK, 1.0])
    parts = bird_parts(BirdPose(nod=20, tilt=-15), radius=34)

    assert parts[1] @ neck == pytest.approx(neck, abs=1e-5)
    assert not np.allclose(parts[1], np.eye(4))
    assert np.allclose(parts[0], np.eye(4))  # the body hasn't moved


def test_squashing_keeps_her_feet_on_the_ground():
    foot = np.array([5.0, 3.0, FEET, 1.0])
    parts = bird_parts(BirdPose(squash=0.85), radius=34)

    squashed = parts[0] @ foot
    assert squashed[2] == pytest.approx(FEET)
    top = parts[0] @ np.array([0.0, 0.0, 30.0, 1.0])
    assert top[2] < 30


def test_hopping_lifts_every_part_together():
    parts = bird_parts(BirdPose(hop=12), radius=34)
    for part in parts:
        assert part[:3, 3][2] == pytest.approx(12)
