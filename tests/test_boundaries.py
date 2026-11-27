"""Import rules: games see only the interface, and the interface needs nothing (ADR 0004)."""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def imported_names(path: Path, root: Path = SRC) -> set[str]:
    """Every module (or module.name) a file imports, with relative imports made absolute."""
    package = ".".join(path.relative_to(root).with_suffix("").parts[:-1])
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package.rsplit(".", node.level - 1)[0] if node.level else ""
            module = ".".join(part for part in (base, node.module) if part)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def _within(name: str, package: str) -> bool:
    return name == package or name.startswith(package + ".")


def forbidden_in_games(names: set[str]) -> set[str]:
    """Games may import anything except OpenCV and Lorikeet's vision code (CLAUDE.md rule 1)."""
    return {
        name
        for name in names
        if _within(name, "cv2")
        or (
            _within(name, "lorikeet")
            and not _within(name, "lorikeet.interface")
            and not _within(name, "lorikeet.games")
        )
    }


def test_interface_imports_only_the_standard_library():
    names = imported_names(SRC / "lorikeet" / "interface.py")

    assert {n for n in names if n.split(".")[0] not in sys.stdlib_module_names} == set()


def test_games_import_only_the_interface():
    for path in (SRC / "lorikeet" / "games").rglob("*.py"):
        assert forbidden_in_games(imported_names(path)) == set(), path


def test_games_rule_catches_opencv_and_vision_imports(tmp_path: Path):
    # games/ is empty until Phase 3, so prove the rule above would fire.
    level = tmp_path / "lorikeet" / "games" / "puzzle" / "level.py"
    level.parent.mkdir(parents=True)
    level.write_text(
        "import cv2\n"
        "import pymunk\n"
        "from ...detection import find_pieces\n"
        "from lorikeet import tracking\n"
        "from lorikeet.interface import Piece\n"
        "from .ball import Ball\n"
    )

    found = forbidden_in_games(imported_names(level, root=tmp_path))

    assert found == {"cv2", "lorikeet.detection.find_pieces", "lorikeet.tracking"}


def test_games_rule_catches_the_input_and_output_choices(tmp_path: Path):
    # A game can't tell the camera from the desk, or a projector from a window, so it can't
    # import the code that makes those choices: the desk, or the launcher that wires it up.
    world = tmp_path / "lorikeet" / "games" / "nest" / "world.py"
    world.parent.mkdir(parents=True)
    world.write_text("from lorikeet.desk.source import DeskSceneSource\nfrom lorikeet import app\n")

    found = forbidden_in_games(imported_names(world, root=tmp_path))

    assert found == {"lorikeet.desk.source.DeskSceneSource", "lorikeet.app"}
