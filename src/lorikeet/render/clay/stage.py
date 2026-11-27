"""The clay set: camera, studio light, backdrop and the clay shader, in Panda3D.

Picture a stop-motion set filmed from straight in front: a backdrop at the back, the clay
figures in front of it, one big softbox up and to the left of the camera as the key light,
and soft light all round as fill. `Stage` builds that inside a Panda3D window or offscreen
buffer, and `figure_node` turns a built `ClayMesh` into something it can draw.

- **Camera.** Orthographic, one world unit per projector pixel, so the 2D game lands on
  the wall exactly (see `coords.py`). Depth still matters for light and shadow.
- **Key light.** A Panda3D directional light with its built-in shadow map. Its lens has to
  be fitted around the playfield: the shadow map only covers what that lens sees, and an
  unfitted lens is the usual reason Panda3D shadows don't appear at all. It's fitted
  tightly, so the map's 4096 texels cover the 1920 px playfield at about two texels per
  pixel and shadow edges stay smooth.
- **Fill.** Not Panda lights: the shader does them (a soft light from all round plus a
  gentle one from the front right), since they don't cast shadows.
- **Backdrop.** A plane at the back that catches the shadows: a muted warm grey, lighter
  at the top, kept nearly colourless because its light lands on every real note.
- **Anti-aliasing.** 8x multisampling, so silhouettes are smooth curves, not stairs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from importlib.resources import files

import numpy as np
from panda3d.core import (
    AntialiasAttrib,
    BitMask32,
    CardMaker,
    ColorBlendAttrib,
    ColorWriteAttrib,
    CullFaceAttrib,
    DirectionalLight,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    LMatrix3f,
    LMatrix4f,
    NodePath,
    OrthographicLens,
    Point3,
    PTA_LMatrix3f,
    PTA_LMatrix4f,
    PTA_LVecBase3f,
    RenderState,
    SamplerState,
    Shader,
    ShaderAttrib,
    Texture,
    Vec3,
)

from lorikeet.render.clay.colour import linear
from lorikeet.render.clay.coords import to_world
from lorikeet.render.clay.detail import TILE, Detail
from lorikeet.render.clay.figure import MAX_CLAYS, MAX_PARTS, ClayMesh

CAMERA_DISTANCE = 1000.0
"""How far in front of the play layer the camera sits. With an orthographic lens this
changes nothing on screen; it only has to be in front of everything."""

BACKDROP_DEPTH = 28.0
"""How far behind the play layer the backdrop is, in pixels. Further back means shadows
land further from what casts them, and softer."""

BACKDROP_TOP, BACKDROP_BOTTOM = (150, 148, 145), (116, 114, 111)
"""A muted, barely warm grey, lighter at the top like a lit studio sweep. The near-white
light is a touch warm too, so on screen it comes out at about 8% saturation (OpenCV S about
20): too little for the camera to take any of it for a note (ADR 0006), even though its hue
is close to yellow's."""

SHADOW_MAP = 4096
"""Shadow map texels per side."""

SEEN = BitMask32.bit(0)
"""Drawn by the camera."""
SHADOWS = BitMask32.bit(1)
"""Drawn into the key light's shadow map. A note's stand-in box is only this: invisible,
but it casts a shadow, as the real paper on the wall would if it stood out from it."""


@dataclass
class Light:
    """The studio light. Angles in degrees."""

    angle: float = -40.0
    """Where the key light comes from, on the wall: 0 is straight above, negative is to
    the left, clockwise like the game's angles. -40 is up and to the left, as in the flat
    looks, so shadows fall down and to the right."""
    tilt: float = 62.0
    """How far round from the camera the key light is: 0 would be right behind the camera
    (flat, no shadows to see), 90 would be skimming along the wall."""
    key: float = 1.0
    """Key brightness."""
    fill: float = 0.15
    """All-round fill brightness. About a sixth of the key: enough that shadows keep their
    colour, little enough that the forms model. Too much fill is what makes things look
    flat-lit."""
    front_fill: float = 0.07
    """The gentle front-right fill's brightness."""

    def toward_key(self) -> np.ndarray:
        """Unit vector, world space, from the set towards the key light."""
        a, t = math.radians(self.angle), math.radians(self.tilt)
        return np.array([math.sin(t) * math.sin(a), -math.cos(t), math.sin(t) * math.cos(a)])


def canvas_camera(size: tuple[int, int]) -> tuple[OrthographicLens, Point3]:
    """The camera's lens and where it stands, so the canvas fills the frame pixel for pixel."""
    width, height = size
    lens = OrthographicLens()
    lens.setFilmSize(width, height)
    lens.setNearFar(1.0, CAMERA_DISTANCE * 3)
    return lens, Point3(width / 2, -CAMERA_DISTANCE, -height / 2)


def close_up(size: tuple[int, int], centre: tuple[float, float], zoom: float):
    """A camera framing `centre` (projector pixels) `zoom` times bigger, for look-dev."""
    width, height = size
    lens = OrthographicLens()
    lens.setFilmSize(width / zoom, height / zoom)
    lens.setNearFar(1.0, CAMERA_DISTANCE * 3)
    x, _, z = to_world(centre)
    return lens, Point3(x, -CAMERA_DISTANCE, z)


class Stage:
    def __init__(self, base, size: tuple[int, int], detail: Detail, light: Light) -> None:
        """Set up the set in a Panda3D ShowBase whose window (or buffer) is `size`."""
        self.base = base
        self.size = size
        self.light = light
        self.root = base.render
        self.root.setAntialias(AntialiasAttrib.MMultisample)

        lens, place = canvas_camera(size)
        base.cam.node().setLens(lens)
        base.cam.node().setCameraMask(SEEN)
        base.cam.setPos(place)
        base.cam.lookAt(place + Vec3(0, 1, 0))

        self.key = DirectionalLight("key")
        self.key.setColor((light.key, light.key * 0.98, light.key * 0.95, 1))  # near white
        self.key.setShadowCaster(True, SHADOW_MAP, SHADOW_MAP)
        self.key.setCameraMask(SHADOWS)
        self.key_np = self.root.attachNewNode(self.key)
        self.root.setLight(self.key_np)
        self._fit_key()

        vert = files("lorikeet.render.clay").joinpath("shaders/clay.vert").read_text()
        frag = files("lorikeet.render.clay").joinpath("shaders/clay.frag").read_text()
        self.root.setShader(Shader.make(Shader.SL_GLSL, vert, frag))
        # The shadow map is drawn by the light's own camera, with the scene's shaders. All it
        # needs is depth, so give it the same vertex shader (poses and boil cast shadows
        # too) and a fragment shader that does nothing. Otherwise the full clay shader would
        # run for every shadow-map pixel, reading the very map it's drawing into. Priority
        # 1000 makes it win over the scene's shader; the scene's inputs still come through.
        # Reverse culling (draw back faces only) and no colour are Panda3D's own defaults
        # for a shadow camera, kept: back faces make the map a little deeper than the
        # surfaces facing the light, which helps against shadow acne.
        depth_only = Shader.make(Shader.SL_GLSL, vert, "#version 330\nvoid main() {}\n")
        self.key.setInitialState(
            RenderState.make(
                CullFaceAttrib.makeReverse(),
                ColorWriteAttrib.make(ColorWriteAttrib.COff),
                ShaderAttrib.make(depth_only, 1000),
            )
        )
        self.root.setShaderInput("detail", _detail_texture(detail))
        self.root.setShaderInput("detail_tile", TILE)
        toward = light.toward_key()
        self.root.setShaderInput("key_toward", Vec3(*toward))
        front = np.array([0.55, -1.0, 0.15])
        self.root.setShaderInput("fill_toward", Vec3(*(front / np.linalg.norm(front))))
        warm = np.array([1.0, 0.96, 0.9])
        self.root.setShaderInput("fill_colour", Vec3(*(warm * light.front_fill)))
        self.root.setShaderInput("sky_colour", Vec3(*(np.array([1.0, 0.98, 0.95]) * light.fill)))
        ground = np.array([1.0, 0.86, 0.72]) * light.fill * 0.45  # bounced off a warm floor
        self.root.setShaderInput("ground_colour", Vec3(*ground))
        self.root.setShaderInput("boil_amount", 0.0)
        self.root.setShaderInput("boil_seed", 0.0)
        self.root.setShaderInput("sheen_strength", 0.6)
        self.root.setShaderInput("shadow_strength", 0.92)
        self.set_softness(self.root, pixels=1.6)
        self.root.setShaderInput("detail_strength", 1.0)
        self.root.setShaderInput("debug_view", 0)
        pose(self.root, [np.eye(4)] * MAX_PARTS)  # nothing posed unless a figure says so

        self.backdrop = self._backdrop()

    def set_softness(self, node: NodePath, pixels: float) -> None:
        """How soft shadows landing on `node` are: the blur radius in pixels.

        Real shadows get softer the further they fall from what casts them. Shadows on the
        backdrop fall furthest, so it gets a wide blur; shadows on figures (a wing on a
        body) fall a short way, so they get a narrow one."""
        lens = self.key.getLens()
        film = max(lens.getFilmSize().x, lens.getFilmSize().y)
        node.setShaderInput("shadow_radius", pixels / film)
        # Step out further for wider blurs: a wide disc of lookups on a curved surface
        # reaches round the curve, where the surface itself would shadow them.
        node.setShaderInput("normal_offset", 0.6 + 0.6 * pixels)
        near, far = lens.getNear(), lens.getFar()
        node.setShaderInput("shadow_bias", 0.4 / (far - near))  # 0.4 px of depth

    def _fit_key(self) -> None:
        """Point the key light at the playfield and fit its lens tightly round it."""
        width, height = self.size
        toward = self.light.toward_key()
        centre = np.array(to_world((width / 2, height / 2), BACKDROP_DEPTH / 2))
        self.key_np.setPos(Point3(*(centre + toward * 2000)))
        self.key_np.lookAt(Point3(*centre))
        # The box everything can be in: the canvas, from well in front of the play layer
        # to the backdrop, with a margin so things at the edge still cast shadows.
        margin = 80
        corners = [
            Point3(*to_world((x, y), depth))
            for x in (-margin, width + margin)
            for y in (-margin, height + margin)
            for depth in (-120, BACKDROP_DEPTH + 2)
        ]
        seen = np.array([tuple(self.key_np.getRelativePoint(self.root, c)) for c in corners])
        low, high = seen.min(axis=0), seen.max(axis=0)
        lens = self.key.getLens()
        lens.setFilmSize(high[0] - low[0], high[2] - low[2])
        lens.setFilmOffset((high[0] + low[0]) / 2, (high[2] + low[2]) / 2)
        lens.setNearFar(low[1] - 10, high[1] + 10)

    def _backdrop(self) -> NodePath:
        """A plane behind everything, lighter at the top, a little lighter where the key
        light points, and darker towards the bottom corners, like a softbox-lit sweep."""
        width, height = self.size
        margin = 200
        columns, rows = 49, 29
        xs = np.linspace(-margin, width + margin, columns)
        ys = np.linspace(-margin, height + margin, rows)
        gx, gy = np.meshgrid(xs, ys)
        u, v = gx / width, gy / height
        top, bottom = np.array(linear(BACKDROP_TOP)), np.array(linear(BACKDROP_BOTTOM))
        fall = np.clip(v, 0, 1) ** 1.3
        albedo = (
            top[None, None, :] * (1 - fall[..., None]) + bottom[None, None, :] * fall[..., None]
        )
        glow = np.exp(-(((u - 0.3) / 0.6) ** 2 + ((v - 0.25) / 0.7) ** 2))
        albedo *= (0.88 + 0.16 * glow)[..., None]
        positions = np.stack([gx, np.full_like(gx, BACKDROP_DEPTH), -gy], axis=-1).reshape(-1, 3)
        normals = np.tile([0.0, -1.0, 0.0], (len(positions), 1))
        index = np.arange(rows * columns).reshape(rows, columns)
        a, b = index[:-1, :-1].ravel(), index[:-1, 1:].ravel()
        c, d = index[1:, 1:].ravel(), index[1:, :-1].ravel()
        triangles = np.concatenate([np.stack([a, d, c], 1), np.stack([a, c, b], 1)])
        # All one "clay", white, with the gradient in the tint.
        distances = np.full((len(positions), MAX_CLAYS), 10.0, dtype=np.float32)
        distances[:, 0] = -1.0
        mesh = ClayMesh(
            positions.astype(np.float32),
            normals.astype(np.float32),
            np.ones(len(positions), dtype=np.float32),
            triangles.astype(np.uint32),
            distances,
            np.ones((MAX_CLAYS, 3), dtype=np.float32),
            albedo.reshape(-1, 3).astype(np.float32),
            np.tile(np.array([1, 0, 0, 0], dtype=np.float32), (len(positions), 1)),
        )
        node = figure_node(mesh, "backdrop")
        node.reparentTo(self.root)
        node.hide(SHADOWS)  # it's behind everything: nothing for it to shadow
        node.setShaderInput("detail_strength", 0.0)
        node.setShaderInput("sheen_strength", 0.0)
        # The softbox is far bigger than a figure, so on the backdrop, well behind it, the
        # figure only ever blocks part of the light: there's no fully dark core.
        node.setShaderInput("shadow_strength", 0.75)
        self.set_softness(node, pixels=5.0)
        return node

    def wall_layer(self) -> NodePath:
        """A card over the whole frame that multiplies the picture by the wall: white where
        the wall is bare, paper where the desk's notes are (see `render/__init__.py`). Set
        its texture with `set_wall`."""
        card = CardMaker("wall")
        card.setFrameFullscreenQuad()
        node = self.base.render2d.attachNewNode(card.generate())
        # Multiply: the new colour is the picture's colour times the card's.
        node.setAttrib(
            ColorBlendAttrib.make(
                ColorBlendAttrib.M_add, ColorBlendAttrib.O_fbuffer_color, ColorBlendAttrib.O_zero
            )
        )
        node.setDepthTest(False)
        node.setDepthWrite(False)
        return node


def pose(node: NodePath, moves: list[np.ndarray]) -> None:
    """Set where each movable part of a figure has moved to: one 4x4 matrix per part (in
    column-vector form, as numpy writes them), body first."""
    moved, turned = PTA_LMatrix4f.emptyArray(MAX_PARTS), PTA_LMatrix3f.emptyArray(MAX_PARTS)
    for i, m in enumerate(moves[:MAX_PARTS]):
        # Panda3D stores matrices transposed (it multiplies row vectors), and hands them to
        # GLSL as stored, so a transposed matrix arrives as the matrix we meant.
        moved[i] = LMatrix4f(*np.asarray(m, dtype=np.float64).T.flatten())
        normal = np.linalg.inv(m[:3, :3]).T
        turned[i] = LMatrix3f(*normal.T.flatten())
    node.setShaderInput("part_move", moved)
    node.setShaderInput("part_turn", turned)


def shadow_box(outline, back: float) -> NodePath:
    """An invisible prism the shape of `outline` (projector pixels around its centre),
    from the play layer back to `back`, that only casts a shadow. Real notes are paper on
    the wall: this lets them cast a soft shadow onto the clay set, starting right at the
    paper's edge. Built directly, not meshed, so a new note costs nothing."""
    ring = np.array([(x, -y) for x, y in outline], dtype=np.float32)
    n = len(ring)
    front = np.stack([ring[:, 0], np.zeros(n), ring[:, 1]], axis=1)
    rear = np.stack([ring[:, 0], np.full(n, back), ring[:, 1]], axis=1)
    positions = np.concatenate([front, rear]).astype(np.float32)
    sides = [(i, (i + 1) % n, n + (i + 1) % n) for i in range(n)]
    sides += [(i, n + (i + 1) % n, n + i) for i in range(n)]
    caps = [(0, i, i + 1) for i in range(1, n - 1)]
    caps += [(n, n + i + 1, n + i) for i in range(1, n - 1)]
    triangles = np.array(sides + caps, dtype=np.uint32)
    count = len(positions)
    mesh = ClayMesh(
        positions,
        np.tile(np.array([0, -1, 0], dtype=np.float32), (count, 1)),
        np.ones(count, dtype=np.float32),
        triangles,
        np.zeros((count, MAX_CLAYS), dtype=np.float32),
        np.ones((MAX_CLAYS, 3), dtype=np.float32),
        np.ones((count, 3), dtype=np.float32),
        np.tile(np.array([1, 0, 0, 0], dtype=np.float32), (count, 1)),
    )
    node = figure_node(mesh, "note shadow")
    node.hide(SEEN)
    node.setTwoSided(True)  # wound either way round, it still blocks the light
    return node


def set_wall(card: NodePath, wall_rgb: bytes, size: tuple[int, int]) -> None:
    """Put the wall (8-bit RGB rows, top row first) on the wall card."""
    width, height = size
    texture = card.getTexture() if card.hasTexture() else None
    if texture is None or texture.getXSize() != width or texture.getYSize() != height:
        texture = Texture("wall")
        texture.setup2dTexture(width, height, Texture.T_unsigned_byte, Texture.F_rgb)
        texture.setMinfilter(SamplerState.FT_nearest)
        texture.setMagfilter(SamplerState.FT_nearest)
        card.setTexture(texture)
    rows = np.frombuffer(wall_rgb, dtype=np.uint8).reshape(height, width, 3)
    # Panda3D textures start at the bottom row, and keep blue, green, red.
    texture.setRamImage(np.ascontiguousarray(rows[::-1, :, ::-1]).tobytes())


_FORMAT: GeomVertexFormat | None = None


def _vertex_format() -> GeomVertexFormat:
    """Per vertex, in one interleaved array of floats: position, normal, colour (rgb: the
    tint, a: occlusion), the distance to each clay in three groups of four, and the weight
    of each movable part. Floats, not the usual 8-bit colour, so the occlusion's soft
    gradients don't step."""
    global _FORMAT
    if _FORMAT is None:
        array = GeomVertexArrayFormat()
        array.addColumn("vertex", 3, Geom.NT_float32, Geom.C_point)
        array.addColumn("normal", 3, Geom.NT_float32, Geom.C_normal)
        array.addColumn("color", 4, Geom.NT_float32, Geom.C_color)
        for group in ("clay_a", "clay_b", "clay_c", "parts"):
            array.addColumn(group, 4, Geom.NT_float32, Geom.C_other)
        _FORMAT = GeomVertexFormat.registerFormat(GeomVertexFormat(array))
    return _FORMAT


def figure_node(mesh: ClayMesh, name: str) -> NodePath:
    """A Panda3D node for a built mesh, with its clay colours. The arrays are copied
    straight into Panda3D's vertex buffer, which is far faster than writing vertices one by
    one from Python."""
    rows = np.concatenate(
        [
            mesh.positions,
            mesh.normals,
            mesh.tint,
            mesh.occlusion[:, None],
            mesh.clay_distances,
            mesh.part_weights,
        ],
        axis=1,
    ).astype(np.float32)
    data = GeomVertexData(name, _vertex_format(), Geom.UH_static)
    data.uncleanSetNumRows(len(rows))
    memoryview(data.modifyArray(0)).cast("B")[:] = rows.tobytes()
    triangles = GeomTriangles(Geom.UH_static)
    triangles.setIndexType(Geom.NT_uint32)
    indices = triangles.modifyVertices()
    indices.uncleanSetNumRows(mesh.triangles.size)
    memoryview(indices).cast("B")[:] = mesh.triangles.astype(np.uint32).tobytes()
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    path = NodePath(node)
    palette = PTA_LVecBase3f.emptyArray(MAX_CLAYS)
    for i, colour in enumerate(mesh.palette):
        palette[i] = tuple(float(c) for c in colour)
    path.setShaderInput("palette", palette)
    return path


def _detail_texture(detail: Detail) -> Texture:
    """The fingerprint texture on the GPU: 16-bit float, so the slopes keep their fine
    gradations, tiling, and mipmapped, so it blurs away smoothly on small things."""
    rgba = detail.rgba()
    size = rgba.shape[0]
    texture = Texture("clay detail")
    texture.setup2dTexture(size, size, Texture.T_float, Texture.F_rgba16)
    # Panda3D keeps texels in blue, green, red, alpha order.
    texture.setRamImage(np.ascontiguousarray(rgba[..., [2, 1, 0, 3]]).tobytes())
    texture.setWrapU(SamplerState.WM_repeat)
    texture.setWrapV(SamplerState.WM_repeat)
    texture.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    texture.setMagfilter(SamplerState.FT_linear)
    texture.setAnisotropicDegree(8)
    return texture
