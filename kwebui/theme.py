"""Theme discovery. Themes are just CSS files under ``themes/``."""

from __future__ import annotations

from pathlib import Path

THEMES_DIR = Path(__file__).parent / "themes"

DEFAULT_THEME = "light"


def available_themes() -> list[str]:
    return sorted(path.stem for path in THEMES_DIR.glob("*.css"))


def theme_path(name: str) -> Path:
    path = THEMES_DIR / f"{name}.css"
    if not path.is_file():
        raise ValueError(f"Unknown theme {name!r}. Available: {', '.join(available_themes())}")
    return path
