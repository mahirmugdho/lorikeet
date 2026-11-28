"""The wall and overlay layer reach the GPU only when they change, copied straight across."""

import numpy as np
import pygame

from lorikeet.render.clay.mirror import Mirror

SIZE = (64, 32)


def texels(mirror: Mirror) -> np.ndarray:
    return np.frombuffer(bytes(mirror.texture.getRamImage()), dtype=np.uint8)


def test_a_surface_is_copied_once_and_again_only_after_it_changes():
    wall = pygame.Surface(SIZE)
    wall.fill((255, 255, 255))
    mirror = Mirror("wall", SIZE)

    assert mirror.update(wall)
    assert not mirror.update(wall)  # nothing new: nothing copied
    pygame.draw.rect(wall, (250, 226, 120), (10, 8, 20, 12))  # a note goes on
    assert mirror.update(wall)
    assert np.array_equal(texels(mirror), np.frombuffer(wall.get_buffer(), dtype=np.uint8))


def test_a_clear_layer_is_known_to_be_empty():
    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    mirror = Mirror("layer", SIZE, every=2)

    mirror.update(layer)
    assert mirror.empty
    pygame.draw.circle(layer, (40, 40, 40, 255), (30, 16), 6)
    mirror.update(layer)
    assert not mirror.empty


def test_a_surface_in_another_format_still_arrives_right():
    odd = pygame.Surface(SIZE, depth=24)
    odd.fill((10, 20, 30))
    mirror = Mirror("odd", SIZE)

    mirror.update(odd)
    blue, green, red = texels(mirror)[:3]
    assert (red, green, blue) == (10, 20, 30)
