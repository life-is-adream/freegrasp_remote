import sys
from pathlib import Path


def ensure_groundingdino_path(project_root: str | Path | None = None) -> bool:
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]
    else:
        project_root = Path(project_root).resolve()

    groundingdino_root = project_root / "models" / "langsam" / "GroundingDINO"
    package_dir = groundingdino_root / "groundingdino"
    if not package_dir.exists():
        return False

    groundingdino_str = str(groundingdino_root)
    if groundingdino_str not in sys.path:
        sys.path.insert(0, groundingdino_str)
        return True
    return False
