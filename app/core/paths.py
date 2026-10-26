"""Path sanitizing and root confinement (R-SAFE-3)."""

import re
from pathlib import Path

MAX_COMPONENT_BYTES = 255
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class PathEscapeError(ValueError):
    """A generated path resolved outside its library root."""


def sanitize_component(name: str) -> str:
    """One path component: no illegal chars, no leading dots, <=255 bytes, never empty."""
    name = _ILLEGAL.sub("-", name)
    name = re.sub(r"\s+", " ", name).strip().lstrip(".").rstrip(". ")
    suffix = Path(name).suffix if len(Path(name).suffix) <= 8 else ""
    stem = name[: len(name) - len(suffix)] if suffix else name
    budget = MAX_COMPONENT_BYTES - len(suffix.encode())
    # truncate on a character boundary, not mid-codepoint
    stem = stem.encode()[:budget].decode(errors="ignore").rstrip(". ")
    return (stem + suffix) or "_"


def confine(root: str | Path, *parts: str) -> Path:
    """Join sanitized parts under root; raise if the result is not inside root."""
    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*(sanitize_component(p) for p in parts))
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root_resolved) or resolved == root_resolved:
        raise PathEscapeError(f"{candidate} escapes {root_resolved}")
    return resolved


def ensure_inside(root: str | Path, path: str | Path) -> Path:
    """Verify an already-built path (e.g. a stored plan target) is inside root."""
    root_resolved = Path(root).resolve()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root_resolved):
        raise PathEscapeError(f"{path} escapes {root_resolved}")
    return resolved
