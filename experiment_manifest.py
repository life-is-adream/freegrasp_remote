"""Immutable provenance contracts for FreeGrasp experiments."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def guard_provenance(route_guard_variant):
    if route_guard_variant == "none":
        return {"route_guard_variant": "none"}
    if route_guard_variant == "conservative_v1":
        from route_guard_config import (
            CONSERVATIVE_GUARD_VERSION,
            DIRECT_CONFIDENCE_THRESHOLD,
            DIRECT_MAX_OBJECT_COUNT,
            TARGET_OVERLAP_THRESHOLD,
        )

        return {
            "route_guard_variant": route_guard_variant,
            "direct_confidence_threshold": DIRECT_CONFIDENCE_THRESHOLD,
            "direct_max_object_count": DIRECT_MAX_OBJECT_COUNT,
            "target_overlap_threshold": TARGET_OVERLAP_THRESHOLD,
            "guard_code_version": CONSERVATIVE_GUARD_VERSION,
        }
    if route_guard_variant == "target_evidence_v2":
        from route_guard_config import (
            DUPLICATE_BBOX_OVERLAP_THRESHOLD,
            DUPLICATE_MASK_IOU_THRESHOLD,
            TARGET_EVIDENCE_GUARD_VERSION,
            TARGET_EVIDENCE_MAX_CANDIDATES,
        )

        return {
            "route_guard_variant": route_guard_variant,
            "target_evidence_max_candidates": (
                TARGET_EVIDENCE_MAX_CANDIDATES
            ),
            "duplicate_mask_iou_threshold": (
                DUPLICATE_MASK_IOU_THRESHOLD
            ),
            "duplicate_bbox_overlap_threshold": (
                DUPLICATE_BBOX_OVERLAP_THRESHOLD
            ),
            "guard_code_version": TARGET_EVIDENCE_GUARD_VERSION,
        }
    raise ValueError(f"Unknown route guard: {route_guard_variant}")


def hash_directory(root):
    digest = hashlib.sha256()
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(root)
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _git_state(cwd="."):
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def build_manifest(config, command=None, cwd="."):
    manifest = dict(config)
    routing = manifest.get("routing_variant", "none")
    if routing != "none" and manifest.get("uses_gt_features", False):
        raise ValueError("Automatic routing cannot use ground-truth features")
    if routing != "none" and manifest.get("uses_benchmark_difficulty", False):
        raise ValueError("Automatic routing cannot use benchmark difficulty")

    commit, dirty = _git_state(cwd)
    manifest.setdefault("git_commit", commit)
    manifest.setdefault("dirty_worktree", dirty)
    manifest.setdefault("command", command)
    canonical = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    manifest["manifest_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    return manifest


def write_manifest(path, manifest, resume=False):
    path = Path(path)
    serialized = json.dumps(manifest, indent=2, sort_keys=True)
    if path.exists():
        existing = json.loads(path.read_text())
        comparable = lambda value: {
            key: item for key, item in value.items() if key != "created_at_utc"
        }
        if not resume or comparable(existing) != comparable(manifest):
            raise FileExistsError(f"Manifest mismatch or overwrite refused: {path}")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        handle.write(serialized)
    return manifest


def count_cache_pairs(root):
    root = Path(root)
    pairs = 0
    for image in root.glob("scene*/*.png"):
        scene_id = image.stem
        if (image.parent / f"{scene_id}_id.txt").exists():
            pairs += 1
    return pairs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    hash_parser = subparsers.add_parser("hash-cache")
    hash_parser.add_argument("path")
    args = parser.parse_args(argv)
    if args.command == "hash-cache":
        print(
            json.dumps(
                {
                    "cache_sha256": hash_directory(args.path),
                    "scene_pairs": count_cache_pairs(args.path),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
