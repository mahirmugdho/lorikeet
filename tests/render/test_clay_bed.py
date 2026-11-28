"""The flower bed waits half open, then blooms when the egg arrives: flowers open one after
another, grow past their size and settle, stems get taller, and hidden buds come up."""

from lorikeet.render.clay.bed import FLOWERS, STEM_GROWTH, flower_state
from lorikeet.render.clay.kinds import FLOWER_STAGES

OPEN = FLOWER_STAGES - 1
MAIN = [i for i, f in enumerate(FLOWERS) if not f.bud]
BUDS = [i for i, f in enumerate(FLOWERS) if f.bud]


def test_before_the_egg_arrives_flowers_are_half_open_and_buds_hidden():
    for frame in range(0, 100, 7):
        for i in MAIN:
            state = flower_state(i, frame, bloomed_at=None)
            assert 0 < state.stage < OPEN and state.scale > 0
        for i in BUDS:
            assert flower_state(i, frame, bloomed_at=None).scale == 0


def test_after_the_egg_arrives_everything_ends_up_open_bigger_and_taller():
    later = 40 + 60  # five seconds after it bloomed at frame 40
    for i in range(len(FLOWERS)):
        state = flower_state(i, later, bloomed_at=40)
        assert state.stage == OPEN
        assert state.scale >= 1.0
    for i in MAIN:
        before = flower_state(i, 39, bloomed_at=None)
        after = flower_state(i, later, bloomed_at=40)
        assert after.scale > before.scale
        assert after.stem == STEM_GROWTH


def test_flowers_bloom_one_after_another_not_all_at_once():
    starts = []
    for i in MAIN:
        frame = 40
        while flower_state(i, frame, bloomed_at=40).stage == flower_state(i, 39, None).stage:
            frame += 1
        starts.append(frame)
    assert len(set(starts)) == len(starts)


def test_a_bloom_overshoots_then_settles():
    i = MAIN[0]
    sizes = [flower_state(i, 40 + k, bloomed_at=40).scale for k in range(30)]
    assert max(sizes) > sizes[-1]  # grew past its final size...
    assert sizes[-1] == sizes[-2]  # ...and settled


def test_flowers_sway_a_little_while_they_wait():
    i = MAIN[1]
    sways = {flower_state(i, frame, None).sway for frame in range(60)}
    assert len(sways) > 10 and max(abs(s) for s in sways) < 4
