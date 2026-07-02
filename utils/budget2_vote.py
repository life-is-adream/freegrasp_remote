def _selected_id(result):
    if not isinstance(result, dict):
        return None
    return result.get("selected_object_id")


def select_budget2_vote_result(first_result, second_result, visible_object_ids):
    visible_ids = set(visible_object_ids or [])
    first_id = _selected_id(first_result)
    second_id = _selected_id(second_result)
    first_valid = first_id in visible_ids
    second_valid = second_id in visible_ids

    selected = first_result
    selected_index = 0
    if first_valid and second_valid:
        if first_id == second_id:
            reason = "same_valid_id_keep_first"
        else:
            reason = "valid_disagreement_keep_first"
    elif first_valid:
        reason = "first_valid_second_invalid"
    elif second_valid:
        selected = second_result
        selected_index = 1
        reason = "second_valid_first_invalid"
    else:
        reason = "both_invalid_keep_first"

    return selected, {
        "first_selected_object_id": first_id,
        "second_selected_object_id": second_id,
        "first_valid": first_valid,
        "second_valid": second_valid,
        "selected_raw_output_index": selected_index,
        "selection_reason": reason,
    }
