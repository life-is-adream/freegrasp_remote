#!/usr/bin/env python3
"""Quick VLM router validation on a few cached scenes."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.scene_router import (
    compute_scene_features,
    route_scene_vlm,
    needs_vlm_fallback,
    SCENE_ROUTER_VERSION,
)


def load_molmo_cache(scene_dir):
    """Load parsed_data from molmo cache."""
    scene_name = scene_dir.name.replace("scene", "")
    id_file = scene_dir / f"{scene_name}_id.txt"
    
    if not id_file.exists():
        return None, None
    
    # Parse id.txt format: molmo_id x y gt_id (with header)
    parsed_data = []
    with open(id_file) as f:
        next(f)  # skip header
        for line in f:
            parts = line.split()
            if len(parts) == 4:
                molmo_id, x, y, gt_id = parts
                parsed_data.append((str(molmo_id), int(x), int(y), str(gt_id)))
    
    return parsed_data, None


def main():
    molmo_root = Path("data/output/molmo_output")
    scenes = sorted(molmo_root.iterdir())[:50]  # First 50 scenes for better stats
    
    print(f"Scene Router Version: {SCENE_ROUTER_VERSION}")
    print(f"Testing on {len(scenes)} scenes\n")
    print("=" * 80)
    
    vlm_needed_count = 0
    route_counts = {"direct": 0, "target_first": 0, "blocker_first": 0}
    
    for scene_dir in scenes:
        if not scene_dir.is_dir():
            continue
        
        parsed_data, visible_ids = load_molmo_cache(scene_dir)
        if not parsed_data:
            print(f"[{scene_dir.name}] SKIP: no cache")
            continue
        
        # Compute geometric features
        features = compute_scene_features(parsed_data, image_shape=(480, 640))
        vlm_needed = needs_vlm_fallback(features.composite_score)
        
        if vlm_needed:
            vlm_needed_count += 1
        
        route_counts[features.route_mode] += 1
        
        print(f"[{scene_dir.name}] obj={features.object_count} comp={features.composite_score:.2f} route={features.route_mode} vlm={'Y' if vlm_needed else 'N'}")
    
    print("=" * 80)
    print("Summary:")
    print(f"  Total scenes: {sum(route_counts.values())}")
    print(f"  Routes: direct={route_counts['direct']}, target_first={route_counts['target_first']}, blocker_first={route_counts['blocker_first']}")
    print(f"  VLM fallback needed: {vlm_needed_count}/{sum(route_counts.values())} ({vlm_needed_count/max(1,sum(route_counts.values()))*100:.1f}%)")
    print()
    print("To run full VLM evaluation:")
    print("  python evaluate_mimo_full_protocol.py --subset-policy scene_complexity_vlm_auto --routing-variant scene_complexity_vlm --splits 0")


if __name__ == "__main__":
    main()
