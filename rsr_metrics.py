def is_reasoning_success(selected_object_id, molmo_to_gt_map, gt_ids):
    if selected_object_id is None:
        return False

    try:
        selected_object_id = int(selected_object_id)
    except (TypeError, ValueError):
        return False

    selected_gt_id = molmo_to_gt_map.get(selected_object_id)
    if selected_gt_id is None:
        return False

    return int(selected_gt_id) in {int(gt_id) for gt_id in gt_ids}
