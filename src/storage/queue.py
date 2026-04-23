from __future__ import annotations

from src.storage import paths


def _ensure() -> None:
    home = paths.get_home()
    home.mkdir(parents=True, exist_ok=True)
    qp = paths.queue_path()
    if not qp.exists():
        qp.touch()


def add(url: str) -> None:
    """Append a URL to the queue. Allows duplicates intentionally."""
    _ensure()
    with paths.queue_path().open("a") as fh:
        fh.write(url.strip() + "\n")


def list_all() -> list[str]:
    """Return every queued URL, in order."""
    qp = paths.queue_path()
    if not qp.exists():
        return []
    return [line.strip() for line in qp.read_text().splitlines() if line.strip()]


def remove(url: str) -> bool:
    """Remove the first occurrence of url from the queue. Returns True if removed."""
    qp = paths.queue_path()
    if not qp.exists():
        return False
    lines = [line.strip() for line in qp.read_text().splitlines() if line.strip()]
    target = url.strip()
    for i, line in enumerate(lines):
        if line == target:
            del lines[i]
            qp.write_text("".join(f"{u}\n" for u in lines))
            return True
    return False


def count() -> int:
    return len(list_all())
