import os
import re
import torch
import base64
import numpy as np
from PIL import Image
from matplotlib import pyplot as plt

try:
    import open3d as o3d
except ImportError:
    o3d = None

try:
    from models.FGC_graspnet.utils.data_utils import create_point_cloud_from_depth_image
except ImportError:
    create_point_cloud_from_depth_image = None

from utils.config import client, langsam_actor, api_key

VALID_MIMO_RETRY_MODES = {
    "none",
    "id_repair",
    "hard_review",
    "target_review",
    "roborefer_verify",
    "candidate_verify",
    "first_grasp_verify",
}
VALID_SEGMENTATION_VARIANTS = {"baseline", "point_retry"}


def get_coordinates(labeled_text, goal_id):
    """
    Extract the (X, Y) coordinates for a given goal_id.
    """
    if isinstance(labeled_text, str):
        lines = labeled_text.strip().split("\n")[1:]  # Skip the header
    elif isinstance(labeled_text, list):
        lines = labeled_text[1:]
    
    for line in lines:
        parts = line.split()
        if int(parts[0]) == goal_id:
            return int(parts[1]), int(parts[2])
    return None  # Return None if not found


def _to_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    return np.asarray(value)


def _mask_to_numpy(mask):
    return np.asarray(_to_numpy(mask)).astype(bool)


def _point_in_mask(mask_np, goal_coor):
    if goal_coor is None:
        return False
    x, y = goal_coor
    if y < 0 or x < 0 or y >= mask_np.shape[0] or x >= mask_np.shape[1]:
        return False
    return bool(mask_np[y, x])


def _mask_area_ratio(mask_np):
    return float(mask_np.sum()) / float(mask_np.size) if mask_np.size else 1.0


def _mask_distance_to_point(mask_np, goal_coor):
    if goal_coor is None:
        return float("inf")
    x, y = goal_coor
    mask_indices = np.column_stack(np.where(mask_np > 0))
    if not mask_indices.size:
        return float("inf")
    distances = np.linalg.norm(mask_indices - np.array([y, x]), axis=1)
    return float(np.min(distances))


def mask_contains_point(mask, goal_coor):
    try:
        return _point_in_mask(_mask_to_numpy(mask), goal_coor)
    except (TypeError, ValueError):
        return False


def get_goal_mask_with_index(
    masks,
    goal_coor,
    prefer_small_containing=False,
    max_area_ratio=None,
):
    """
    Select the best mask (and its index) that contains the goal coordinate.
    If none contain the coordinate, select the closest one.
    Returns (None, None) if no valid mask is found.
    """
    if masks is None or len(masks) == 0:
        return None, None
    if goal_coor is None:
        return masks[0], 0

    x, y = goal_coor
    best_mask = None
    selected_index = None
    min_distance = float('inf')
    containing_candidates = []

    for idx, mask in enumerate(masks):
        mask_np = _mask_to_numpy(mask)
        contains_point = _point_in_mask(mask_np, (x, y))
        area_ratio = _mask_area_ratio(mask_np)
        if contains_point:
            if not prefer_small_containing:
                return mask, idx
            containing_candidates.append((area_ratio, mask, idx))
            continue

        # If not inside, compute the minimum distance from goal_coor to mask pixels
        min_dist = _mask_distance_to_point(mask_np, (x, y))
        if min_dist < min_distance:
            min_distance = min_dist
            best_mask = mask
            selected_index = idx

    if containing_candidates:
        filtered = [
            candidate
            for candidate in containing_candidates
            if max_area_ratio is None or candidate[0] <= max_area_ratio
        ]
        candidates = filtered or containing_candidates
        _, selected_mask, selected_idx = min(candidates, key=lambda item: item[0])
        return selected_mask, selected_idx

    return best_mask, selected_index


def visualize_cropping_box(image, cropping_box):
    # Visualize the cropping box on the image
    x1, y1, x2, y2 = cropping_box
    plt.figure()
    plt.imshow(image)
    plt.gca().add_patch(plt.Rectangle((x1, y1), x2-x1,
                                      y2-y1, edgecolor='red', facecolor='none'))
    plt.title("Cropping Box Visualization")
    plt.show()


# Helper functions
def load_image_as_base64(image_path):
    with open(image_path, 'rb') as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    return base64_image



def process_grasping_result(output, text):
    """
    Parses the grasping result output and extracts object ID and class name.

    Supports two formats:
    - "[ID, class name]"  -> Example: "[1, green cylinder]"
    - "[pick object, ID, class name]"  -> Example: "[pick object, 4, blue bolt]"
    """

    json_match = re.search(r"\{.*\}", output, flags=re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data.get("first_grasp_decision"), dict):
                decision = data["first_grasp_decision"]
                object_id = int(
                    decision.get(
                        "first_grasp_object_id",
                        decision.get("object_id", decision.get("selected_object_id")),
                    )
                )
                include_reasoning_json = True
            else:
                decision = data.get("decision") if isinstance(data.get("decision"), dict) else data
                object_id = int(decision.get("object_id", decision.get("selected_object_id")))
                include_reasoning_json = isinstance(data.get("decision"), dict)
            class_name = str(decision.get("class_name", decision.get("mask_query", text))).lower()
            result = {
                "selected_object_id": object_id,
                "class_name": class_name,
            }
            if "mask_query" in decision:
                result["mask_query"] = str(decision["mask_query"]).lower()
            if include_reasoning_json:
                result["reasoning_json"] = data
            return result
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    # Try first format: [ID, class name]
    match1 = re.search(r'\[(\d+),\s*(.+?)\]', output)
    
    # Try second format: [pick object, ID, class name]
    match2 = re.search(r'\[pick object,\s*(\d+),\s*(.+?)\]', output)

    if match1:
        object_id = int(match1.group(1))
        class_name = match1.group(2).lower()
    elif match2:
        object_id = int(match2.group(1))
        class_name = match2.group(2).lower()
    else:
        class_name = text
        return {"class_name": class_name}
    
    return {
        "selected_object_id": object_id,  # Target object ID
        "class_name": class_name  # Target object class name
    }


def _clean_query_text(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"^\s*(pick object|remove obstacle)\s*,?\s*", "", text)
    text = re.sub(r"^[\[\(\{]\s*\d+\s*,\s*", "", text)
    text = re.sub(r"[\]\)\}\.]+$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_langsam_query_candidates(class_name, annotation=None):
    candidates = []

    def add(candidate):
        candidate = _clean_query_text(candidate)
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(class_name)

    base = _clean_query_text(class_name)
    relation_phrases = [
        " under ",
        " underneath ",
        " below ",
        " behind ",
        " on top of ",
        " on the ",
        " on ",
        " near ",
        " next to ",
        " left of ",
        " right of ",
        " in front of ",
        " with ",
    ]
    shortened = base
    for phrase in relation_phrases:
        if phrase in shortened:
            shortened = shortened.split(phrase, 1)[0].strip()
            break
    add(shortened)

    words = shortened.split()
    if len(words) >= 2:
        add(" ".join(words[-2:]))
    if len(words) >= 1:
        add(words[-1])

    if annotation:
        annotation_text = _clean_query_text(annotation)
        annotation_text = re.sub(r"^(grasp|pick|grab|remove)\s+(the\s+|a\s+|an\s+)?", "", annotation_text)
        add(annotation_text)

    return candidates or [_clean_query_text(class_name) or _clean_query_text(annotation)]



def create_cropping_box_from_boxes(box, image_size, margin=20):
    if len(box) == 0:
        return 0, 0, image_size[0], image_size[1]

    x1_min = float('inf')
    y1_min = float('inf')
    x2_max = float('-inf')
    y2_max = float('-inf')

    x1, y1, x2, y2 = box
    if x1 < x1_min:
        x1_min = x1
    if y1 < y1_min:
        y1_min = y1
    if x2 > x2_max:
        x2_max = x2
    if y2 > y2_max:
        y2_max = y2

    x1_min = max(0, x1_min - margin)
    y1_min = max(0, y1_min - margin)
    x2_max = min(image_size[0], x2_max + margin)
    y2_max = min(image_size[1], y2_max + margin)

    return int(x1_min), int(y1_min), int(x2_max), int(y2_max)



def get_and_process_data(cropping_box, color, depth, camera, viz):
    kernel = 0.2

    color = Image.fromarray(color)
    color = np.array(color, dtype=np.float32) / 255.0

    cloud = create_point_cloud_from_depth_image(depth, camera, organized=True)

    x1, y1, x2, y2 = map(int, cropping_box)
    x1_, y1_, x2_, y2_ = x1 - int((x2 - x1) * kernel) - 50, y1 - int((y2 - y1) * kernel) - 50, x2 + int(
        (x2 - x1) * kernel) + 50, y2 + int((y2 - y1) * kernel) + 50

    xmin, ymin, xmax, ymax = 0, 0, camera.width, camera.height
    dx1, dy1, dx2, dy2 = max(x1_, xmin), max(
        y1_, ymin), min(x2_, xmax), min(y2_, ymax)
    print(x1_, y1_, x2_, y2_, xmin, ymin, xmax, ymax)

    mask = np.zeros_like(depth)

    mask[dy1:dy2, dx1:dx2] = 1
    mask = (mask > 0) & (depth > 0)
    cloud_masked = cloud[mask]
    color_masked = color[mask]

    print("Point cloud number", len(cloud_masked))

    num_point = 20000
    if len(cloud_masked) >= num_point:
        idxs = np.random.choice(len(cloud_masked), num_point, replace=False)
    else:
        idxs1 = np.arange(len(cloud_masked))
        idxs2 = np.random.choice(
            len(cloud_masked), num_point - len(cloud_masked), replace=True)
        idxs = np.concatenate([idxs1, idxs2], axis=0)
    
    cloud_sampled = cloud_masked[idxs]
    color_sampled = color_masked[idxs]

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(cloud_sampled.astype(np.float32))
    cloud.colors = o3d.utility.Vector3dVector(color_sampled.astype(np.float32))

    end_points = dict()
    cloud_sampled = torch.from_numpy(
        cloud_sampled[np.newaxis].astype(np.float32))
    cloud_sampled = cloud_sampled.to(device=torch.device(
        'cuda' if torch.cuda.is_available() else 'cpu'))  

    end_points['point_clouds'] = cloud_sampled
    end_points['cloud_colors'] = color_sampled
    if viz:
        o3d.visualization.draw_geometries([cloud])

    return end_points, cloud



### REASONING UTILS ### 
def parse_points_with_id(file_path):
    """Reads the saved sceneXXX_id.txt file and extracts Molmo IDs with GT IDs directly."""
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: {file_path} not found!")

    with open(file_path, 'r') as file:
        lines = file.readlines()

    parsed_data = []
    molmo_to_gt_map = {}  # Direct mapping from Molmo ID → GT ID

    for line in lines[1:]:  # Skip header
        parts = line.split()
        if len(parts) == 4:  # Ensure correct format: "Molmo_ID X Y GT_ID"
            molmo_id, x, y, gt_id = map(int, parts)
            parsed_data.append((molmo_id, x, y, gt_id))
            molmo_to_gt_map[molmo_id] = gt_id  # Store direct mapping

    return parsed_data, molmo_to_gt_map, lines


def _get_candidate_grasp_json_prompt(include_fewshot=False):
    prompt = (
        "You are a first-step robotic grasp planner for bin picking with a parallel gripper. "
        "You will see an RGB image with visible numeric object IDs and a text table listing each visible ID with its point location.\n\n"
        "Your task is NOT merely to identify the requested target. Your task is to output the first visible object to grasp "
        "so the robot can eventually pick the requested target.\n\n"
        "Return exactly one compact JSON object with this schema and no markdown:\n"
        "{\"requested_target\":{\"category\":\"\",\"color\":\"\",\"spatial_terms\":[],\"relation_terms\":[],"
        "\"target_candidate_id\":null,\"visibility\":\"visible/partially_occluded/occluded/uncertain\"},"
        "\"candidate_analysis\":[{\"object_id\":0,\"role\":\"requested_target/direct_obstructor/distractor/uncertain\","
        "\"free\":\"yes/no/uncertain\",\"why\":\"short phrase\"}],"
        "\"first_grasp_decision\":{\"action\":\"pick_target/remove_obstructor\",\"first_grasp_object_id\":0,"
        "\"role\":\"requested_target/direct_obstructor\",\"class_name\":\"short noun phrase\","
        "\"mask_query\":\"short segmentation phrase\",\"confidence\":0.0}}.\n\n"
        "Rules:\n"
        "- requested_target.target_candidate_id is the visible ID that best matches the user request, or null if unclear/hidden.\n"
        "- first_grasp_decision.first_grasp_object_id is the visible object to grasp FIRST. This may differ from target_candidate_id.\n"
        "- If the requested target is visible and free, first_grasp_object_id must be the target ID and action must be pick_target.\n"
        "- If the requested target is under, behind, covered by, or physically blocked by another visible object, choose the direct_obstructor first and action must be remove_obstructor.\n"
        "- Do not choose a nearby distractor unless it directly blocks access to the requested target.\n"
        "- candidate_analysis should cover every visible object ID; each why phrase must be 5 words or fewer.\n"
        "- mask_query must name only the chosen first-grasp object's color and object noun, never a relation sentence.\n"
        "- Do not include location words in mask_query: left, right, top, bottom, center, middle, nearest, farthest, above, below, under.\n"
        "- Return ONLY the JSON object."
    )
    if not include_fewshot:
        return prompt

    return (
        prompt
        + "\n\nFew-shot hard examples. Examples are not the current image; do not copy IDs.\n"
        "Example 1 request: \"the white box in the middle under the toothpaste and screwdriver\". "
        "Pattern: the requested white box is not the first grasp object. Correct first grasp is the direct obstructor: "
        "orange toothpaste box. Use action remove_obstructor, role direct_obstructor, mask_query \"orange toothpaste box\".\n"
        "Example 2 request: \"the cable\". Pattern: the cable target is blocked by a visible tool. Correct first grasp can be "
        "yellow pliers when it directly covers the cable. Use action remove_obstructor and mask_query \"yellow pliers\".\n"
        "Example 3 request: \"the white box on the right-hand side under the chewing gum box\". Pattern: first remove the "
        "blue chewing gum box directly covering access to the requested white box. Use mask_query \"blue chewing gum box\".\n"
        "Example 4 caution: words like under, behind, nearest, top, or bottom are spatial clues, not automatic commands. "
        "Only select a different first_grasp_object_id when that object physically blocks access to the requested target."
    )


def get_reasoning_system_prompt(prompt_variant="legacy"):
    if prompt_variant == "visible_id_guard":
        return (
            "You are a robotic system for bin picking, using a parallel gripper. "
            "I labeled all visible numeric object IDs in the image. Choose the first visible object that should be grasped. "
            "Use the target description together with color, object category, and simple spatial words such as left, right, "
            "top, bottom, center, near, and under. If the target object is visible and free, return the target object ID itself. "
            "If the target is occluded, return one visible free object that directly blocks or covers the target. "
            "Do not choose a nearby distractor. The object_id must be one of the visible numeric object IDs listed in the prompt. "
            "Return exactly one line in this format: [object_id, color class_name]\n"
            "Do not explain. Do not include reasoning. Do not include markdown."
        )
    if prompt_variant == "roborefer_json":
        return (
            "You are a RoboRefer-style spatial reasoning module for robotic bin picking. "
            "You will see an RGB image with visible numeric object IDs and a text table of the same visible IDs. "
            "Use the image, object labels, point locations, target description, spatial relations, and occlusion clues "
            "to decide the first visible object that should be grasped. If the requested target is visible and free, "
            "choose the target. If the target is partially or fully occluded, choose one visible free object that "
            "directly blocks or occludes access to the target. Do not choose nearby distractors.\n"
            "Return exactly one JSON object with this schema and no markdown:\n"
            "{\"target_parse\":{\"category\":\"\",\"color\":\"\",\"spatial_terms\":[],\"relation_terms\":[],"
            "\"requires_obstruction_reasoning\":true},"
            "\"candidate_analysis\":[{\"object_id\":0,\"target_match\":\"yes/no/uncertain\","
            "\"spatial_match\":\"yes/no/uncertain\",\"occlusion_role\":\"free_target/occluded_target/obstructor/distractor\","
            "\"evidence\":\"\",\"reject_reason\":\"\"}],"
            "\"decision\":{\"action\":\"pick_target/remove_obstructor\",\"object_id\":0,"
            "\"class_name\":\"short noun phrase\",\"mask_query\":\"short segmentation phrase\",\"confidence\":0.0}}. "
            "The candidate_analysis array must mention every visible object ID from the text table. "
            "The decision.object_id must be one of the visible object IDs. "
            "The decision.mask_query must be a short visual noun phrase suitable for LangSAM, not a long relation sentence."
        )
    if prompt_variant == "candidate_reasoning_json":
        return (
            "You are a robotic grasping planner for bin picking with a parallel gripper. "
            "You will see an RGB image with visible numeric object IDs and a text table listing each visible ID with its point location.\n\n"
            "Your task: decide which visible object to grasp first to eventually pick the requested target.\n\n"
            "You MUST produce exactly one JSON object with three sections:\n\n"
            "1. target_parse — decompose the request into structured fields:\n"
            "   - category: object category (e.g. \"bandage\", \"cup\")\n"
            "   - color: color or empty string\n"
            "   - spatial_terms: list of spatial words from the request (e.g. [\"left\", \"under\"])\n"
            "   - relation_terms: list of relational phrases (e.g. [\"on top of\", \"near\"])\n"
            "   - requires_obstruction_reasoning: true if the target might be occluded\n\n"
            "2. candidate_analysis — for EVERY visible object ID from the text table, state:\n"
            "   - object_id: the numeric ID\n"
            "   - target_match: \"yes\" if this IS the target, \"no\" if clearly not, \"uncertain\" if unsure\n"
            "   - spatial_match: \"yes\" / \"no\" / \"uncertain\" for spatial constraint match\n"
            "   - occlusion_role: exactly one of \"free_target\", \"occluded_target\", \"obstructor\", \"distractor\"\n"
            "   - evidence: one short phrase explaining why\n"
            "   - reject_reason: empty string if kept as candidate, otherwise why rejected\n\n"
            "3. decision — your final choice:\n"
            "   - action: \"pick_target\" if the target is visible and free, \"remove_obstructor\" if an obstacle must move first\n"
            "   - object_id: integer, must be one of the visible IDs\n"
            "   - class_name: short noun phrase for the chosen object (e.g. \"red cup\")\n"
            "   - mask_query: short visual phrase for LangSAM segmentation (e.g. \"red cup\"), NEVER a long relation sentence\n"
            "   - confidence: float 0.0–1.0\n\n"
            "Rules:\n"
            "- candidate_analysis MUST list ALL visible object IDs. Do not skip any.\n"
            "- If the target is visible and free of obstacles, choose it directly (action=\"pick_target\").\n"
            "- If the target is occluded, choose the visible object that DIRECTLY blocks it (action=\"remove_obstructor\").\n"
            "- Do NOT choose a nearby distractor that merely coexists with the target.\n"
            "- mask_query must be a short visual noun phrase (e.g. \"blue cylinder\"), not a relational description.\n"
            "- Return ONLY the JSON object. No markdown fences, no explanation."
        )
    if prompt_variant == "candidate_grasp_json":
        return _get_candidate_grasp_json_prompt(include_fewshot=False)
    if prompt_variant == "candidate_grasp_fewshot_json":
        return _get_candidate_grasp_json_prompt(include_fewshot=True)
    if prompt_variant == "candidate_grasp_spatial_json":
        return (
            _get_candidate_grasp_json_prompt(include_fewshot=True)
            + "\n\nUse the spatial candidate table fields carefully: image_region, x_rank, y_rank, "
            "bottom_rank, and center_rank are computed from visible Molmo points and are meant to resolve "
            "phrases such as left, right, top, bottom, nearest to image bottom, center, and same-class spatial order."
        )
    if prompt_variant == "json":
        return (
            "You are a robotic system for bin picking, using a parallel gripper. "
            "I labeled all object ids in the image. Return exactly one JSON object: "
            "{\"object_id\": <integer>, \"class_name\": \"<short noun phrase>\"}. "
            "The object_id must be the first object that needs to be grasped to enable "
            "picking the target object. If the target object is free of obstacles, return "
            "the target object ID itself. Otherwise, identify a free object that occludes it. "
            "Do not explain. Do not include markdown."
        )
    if prompt_variant == "direct_target":
        return (
            "You are a robotic system for bin picking, using a parallel gripper. "
            "I labeled all visible numeric object IDs in the image. Choose the visible object ID "
            "that best matches the requested target description. Use color, object category, and spatial words "
            "such as left, right, top, bottom, middle, nearest, and farthest to disambiguate. "
            "Do not choose an obstacle or a covering object merely because it blocks the target. "
            "Return the target object itself whenever it has a visible label. "
            "Return exactly one line in this format: [object_id, color class_name]\n"
            "Do not explain. Do not include reasoning. Do not include markdown."
        )
    if prompt_variant == "hard_occlusion":
        return (
            "You are a robotic system for bin picking, using a parallel gripper. "
            "I labeled all visible numeric object IDs in the image. Some target objects may be fully occluded, "
            "so the target itself may not have a visible label. Your job is to choose the first visible free object "
            "that should be grasped to enable picking the requested target. If the target object is visible and free "
            "of obstacles, return the target object ID itself. If the target is partially or fully occluded, return "
            "one visible free object that occludes or blocks access to it. The object_id must be one of the visible "
            "numeric object IDs in the image. Return exactly one line in this format: [object_id, color class_name]\n"
            "Do not explain. Do not include reasoning. Do not include markdown."
        )
    if prompt_variant in {"legacy", "legacy_old"}:
        legacy_prompt = (
            "You are a robotic system for bin picking, using a parallel gripper. I labeled all objects id in the image."

            "You have two possible actions:"

            "1. remove obstacle, object_id: This action moves the specified object out of the way so it does not interfere with grasping the desired target object. This action can only be performed if the specified object is free of obstacles (not occluded by any other object)."
            "2. pick object, object_id: This action picks up the specified object. It can only be performed if the object is free of obstacles."
            "An object is considered an obstacle if it occludes another object."

            "Task:"
            "Given a target object description as input, determine the first object that needs to be grasped to enable picking the target object. If the target object is free of obstacles, return the target object ID itself. Otherwise, identify an object that is occluding the target and is itself free of obstacles. If multiple objects could be removed, return any one valid option."

            "Output Format:"
        )
    if prompt_variant == "legacy_old":
        return legacy_prompt + (
            "The output should only be the object ID of the first object to grasp, must formatted as: [object_id, color class_name]\n"
        )
    if prompt_variant == "legacy":
        return legacy_prompt + (
            "Return exactly one line in this format: [object_id, color class_name]\n"
            "Do not explain. Do not include reasoning. Do not include markdown."
        )
    raise ValueError(f"Unknown prompt_variant: {prompt_variant}")


def _make_reasoning_messages(system_prompt, user_text, base64_image):
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            ],
        },
    ]


def _call_reasoning_model(messages, model_name, max_output_tokens):
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0,
        max_tokens=max_output_tokens,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        seed=0,
    )
    return response.choices[0].message.content or ""


def _needs_id_repair(result, visible_object_ids):
    selected_id = result.get("selected_object_id")
    return selected_id is None or selected_id not in visible_object_ids


def _build_id_repair_text(input_text, visible_object_ids, previous_output):
    visible_ids = ", ".join(str(object_id) for object_id in visible_object_ids)
    return (
        f"{input_text}\n\n"
        f"Previous answer was invalid: {previous_output}\n"
        f"Visible object IDs: {visible_ids}\n"
        "Choose exactly one object_id from the visible object IDs above. "
        "If the requested target is not visible or is occluded, choose the first visible free object "
        "that must be removed to make the target graspable. "
        "Return exactly one line in this format: [object_id, color class_name]. "
        "Do not explain."
    )


def _is_hard_subset(evaluation_subset):
    return str(evaluation_subset or "").startswith("hard")


def _build_hard_review_text(input_text, visible_object_ids, previous_output):
    visible_ids = ", ".join(str(object_id) for object_id in visible_object_ids)
    return (
        f"{input_text}\n\n"
        f"Previous answer: {previous_output}\n"
        f"Visible object IDs: {visible_ids}\n"
        "Review the previous answer for a hard occlusion scene. First identify the requested target. "
        "Then decide whether the target itself is free, partially occluded, or fully occluded. "
        "If the target is free, return the target ID. If the target is occluded or underneath another object, "
        "return one visible free object that directly blocks or occludes access to the target. "
        "The object_id must be one of the visible object IDs above. "
        "Return exactly one line in this format: [object_id, color class_name]. Do not explain."
    )


def _build_target_review_text(input_text, visible_object_ids, previous_output):
    visible_ids = ", ".join(str(object_id) for object_id in visible_object_ids)
    return (
        f"{input_text}\n\n"
        f"Previous answer: {previous_output}\n"
        f"Visible object IDs: {visible_ids}\n"
        "Re-evaluate the target identity and numeric label carefully. Spatial words use image coordinates: "
        "left/right/top/bottom mean left/right/top/bottom in the image. Prefer the visible object ID that best "
        "matches the requested target description by object category, color, and spatial relation. "
        "Only choose a different object if it is directly on top of or physically occluding the requested target "
        "and must be removed before the target can be grasped. Do not choose a nearby object just because it is "
        "close to the target. The object_id must be one of the visible object IDs above. "
        "Return exactly one line in this format: [object_id, color class_name]. Do not explain."
    )


def _rank_lookup(values, reverse=False):
    ordered = sorted(enumerate(values), key=lambda item: item[1], reverse=reverse)
    return {index: rank + 1 for rank, (index, _value) in enumerate(ordered)}


def _rank_bucket(rank, total, low_name, mid_name, high_name):
    if total <= 1:
        return mid_name
    ratio = (rank - 1) / (total - 1)
    if ratio <= 1 / 3:
        return low_name
    if ratio >= 2 / 3:
        return high_name
    return mid_name


def _candidate_spatial_features(parsed_data):
    if not parsed_data:
        return []

    xs = [x for _molmo_id, x, _y, _gt_id in parsed_data]
    ys = [y for _molmo_id, _x, y, _gt_id in parsed_data]
    total = len(parsed_data)
    x_ranks = _rank_lookup(xs)
    y_ranks = _rank_lookup(ys)
    bottom_ranks = _rank_lookup(ys, reverse=True)

    center_x = (min(xs) + max(xs)) / 2
    center_y = (min(ys) + max(ys)) / 2
    center_distances = [
        (x - center_x) ** 2 + (y - center_y) ** 2
        for _molmo_id, x, y, _gt_id in parsed_data
    ]
    center_ranks = _rank_lookup(center_distances)

    features = []
    for index, (molmo_id, x, y, _gt_id) in enumerate(parsed_data):
        x_rank = x_ranks[index]
        y_rank = y_ranks[index]
        horizontal = _rank_bucket(x_rank, total, "left", "center", "right")
        vertical = _rank_bucket(y_rank, total, "top", "center", "bottom")
        region = "center" if horizontal == "center" and vertical == "center" else f"{vertical}-{horizontal}"
        features.append(
            {
                "id": molmo_id,
                "x": x,
                "y": y,
                "region": region,
                "x_rank": x_rank,
                "y_rank": y_rank,
                "bottom_rank": bottom_ranks[index],
                "center_rank": center_ranks[index],
                "total": total,
            }
        )
    return features


def _format_visible_object_candidates(parsed_data, include_spatial=False):
    lines = ["Visible object candidates from Molmo:"]
    if include_spatial:
        for item in _candidate_spatial_features(parsed_data):
            total = item["total"]
            lines.append(
                f"- id={item['id']}, point=({item['x']}, {item['y']}), "
                f"region={item['region']}, x_rank={item['x_rank']}/{total}, "
                f"y_rank={item['y_rank']}/{total}, bottom_rank={item['bottom_rank']}/{total}, "
                f"center_rank={item['center_rank']}/{total}"
            )
    else:
        for molmo_id, x, y, _gt_id in parsed_data:
            lines.append(f"- id={molmo_id}, point=({x}, {y})")
    return "\n".join(lines)


def _format_first_grasp_rule_reminder():
    return (
        "First-grasp rule reminder:\n"
        "- requested_target_id / target_candidate_id means the object described by the user.\n"
        "- first_grasp_object_id means the first visible object to grasp now.\n"
        "- In hard occlusion scenes these IDs can differ; choose a different ID only for a direct physical blocker."
    )


def _format_spatial_rank_reminder():
    return (
        "Spatial rank reminder:\n"
        "- x_rank=1 is leftmost; larger x_rank is farther right.\n"
        "- y_rank=1 is topmost; larger y_rank is lower in the image.\n"
        "- bottom_rank=1 is nearest to the image bottom.\n"
        "- center_rank=1 is nearest to the visible candidate center."
    )


def _build_reasoning_input_text(input_text, parsed_data, prompt_variant):
    if prompt_variant in {
        "roborefer_json",
        "candidate_reasoning_json",
        "candidate_grasp_json",
        "candidate_grasp_fewshot_json",
        "candidate_grasp_spatial_json",
    }:
        include_spatial = prompt_variant == "candidate_grasp_spatial_json"
        candidate_text = _format_visible_object_candidates(parsed_data, include_spatial=include_spatial)
        if prompt_variant in {"candidate_grasp_fewshot_json", "candidate_grasp_spatial_json"}:
            candidate_text = f"{candidate_text}\n\n{_format_first_grasp_rule_reminder()}"
        if prompt_variant == "candidate_grasp_spatial_json":
            candidate_text = f"{candidate_text}\n\n{_format_spatial_rank_reminder()}"
        return f"{input_text}\n\n{candidate_text}"
    if prompt_variant == "visible_id_guard":
        visible_ids = ", ".join(str(molmo_id) for molmo_id, _x, _y, _gt_id in parsed_data)
        points = "; ".join(f"id={molmo_id}@({x},{y})" for molmo_id, x, y, _gt_id in parsed_data)
        return (
            f"{input_text}\n\n"
            f"Visible object IDs: {visible_ids}\n"
            f"Visible points: {points}"
        )
    return input_text


def _build_roborefer_verify_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous RoboRefer-style JSON:\n{previous_output}\n\n"
        "Verify the previous RoboRefer-style JSON for a hard spatial/occlusion scene. "
        "Check whether it identified the requested target correctly, whether it confused the target with a nearby "
        "distractor, whether the selected object directly blocks the target when removal is needed, and whether "
        "decision.object_id is visible. Return corrected JSON only, using the same schema. Do not include markdown."
    )


def _build_roborefer_id_repair_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous answer was invalid or did not choose a visible object ID:\n{previous_output}\n\n"
        "Choose exactly one decision.object_id from the visible object candidates above. "
        "Return corrected JSON only, using the RoboRefer schema. Do not include markdown."
    )


def _build_candidate_verify_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous candidate reasoning JSON:\n{previous_output}\n\n"
        "Verify the previous JSON for correctness:\n"
        "1. Did candidate_analysis correctly identify the requested target?\n"
        "2. Did it confuse the target with a nearby distractor?\n"
        "3. If the target is occluded, is the selected object_id directly blocking it?\n"
        "4. Is decision.object_id one of the visible object IDs?\n"
        "5. Is decision.mask_query a short visual noun phrase (not a long relation sentence)?\n\n"
        "If any check fails, correct the JSON. Return the corrected JSON only, "
        "using the same candidate_reasoning_json schema. No markdown fences."
    )


def _build_candidate_id_repair_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous answer had an invalid or missing object_id:\n{previous_output}\n\n"
        "Choose exactly one visible object ID from the candidates above. "
        "Return corrected JSON only, using the candidate_reasoning_json schema. Do not include markdown."
    )


def _build_first_grasp_verify_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous candidate grasp JSON:\n{previous_output}\n\n"
        "Verify the previous JSON as a first-step grasp planner, not merely the requested target identifier.\n"
        "Check:\n"
        "1. Did requested_target identify the object described by the user?\n"
        "2. Is first_grasp_decision.first_grasp_object_id the first visible object to grasp?\n"
        "3. If the requested target is under, behind, covered, or blocked, did it choose the direct_obstructor first?\n"
        "4. Did it avoid nearby distractors that do not directly block access?\n"
        "5. Is first_grasp_object_id one of the visible object IDs and is mask_query a short visual noun phrase?\n\n"
        "If any check fails, correct the JSON. Return corrected JSON only, "
        "using the candidate_grasp_json schema. No markdown fences."
    )


def _build_first_grasp_id_repair_text(input_text, parsed_data, previous_output):
    return (
        f"{input_text}\n\n"
        f"{_format_visible_object_candidates(parsed_data)}\n\n"
        f"Previous answer had an invalid or missing first_grasp_object_id:\n{previous_output}\n\n"
        "Choose exactly one visible object ID as first_grasp_decision.first_grasp_object_id. "
        "It must be the first visible object to grasp, not necessarily the requested target object. "
        "Return corrected JSON only, using the candidate_grasp_json schema. Do not include markdown."
    )


def _num_masks(masks):
    if masks is None:
        return 0
    if hasattr(masks, "numel") and masks.numel() == 0:
        return 0
    return len(masks)


def _box_to_numpy(box):
    return np.asarray(_to_numpy(box))


def _select_best_logit_mask(masks, boxes, logits):
    if _num_masks(masks) == 0:
        return None, None, None
    logits_np = np.asarray(_to_numpy(logits))
    best_index = int(np.argmax(logits_np)) if logits_np.size else 0
    return masks[best_index], _box_to_numpy(boxes[best_index]), best_index


def _predict_langsam_mask(image_pil, query_candidates, goal_coor, segmentation_variant):
    if segmentation_variant not in VALID_SEGMENTATION_VARIANTS:
        raise ValueError(f"Unknown segmentation_variant: {segmentation_variant}")

    attempts = []
    fallback = None
    fallback_metadata = None
    candidates = [candidate for candidate in query_candidates if candidate]

    for query in candidates:
        masks, boxes, phrases, logits = langsam_actor.predict(image_pil, query)
        attempt = {
            "query": query,
            "num_masks": _num_masks(masks),
        }
        attempts.append(attempt)

        if _num_masks(masks) == 0:
            attempt["failure_reason"] = "no_masks"
            continue

        if goal_coor is None:
            goal_mask, goal_bbox, mask_index = _select_best_logit_mask(masks, boxes, logits)
            attempt["selected_mask_index"] = mask_index
            metadata = {
                "langsam_queries": [item["query"] for item in attempts],
                "langsam_attempts": attempts,
                "langsam_selected_query": query,
                "langsam_selected_mask_index": mask_index,
                "langsam_mask_contains_point": None,
                "langsam_failure_reason": None,
            }
            return goal_mask, goal_bbox, metadata

        goal_mask, mask_index = get_goal_mask_with_index(
            masks,
            goal_coor,
            prefer_small_containing=segmentation_variant == "point_retry",
            max_area_ratio=0.65 if segmentation_variant == "point_retry" else None,
        )
        attempt["selected_mask_index"] = mask_index
        contains_point = (
            goal_mask is not None
            and segmentation_variant == "point_retry"
            and mask_contains_point(goal_mask, goal_coor)
        )
        attempt["contains_molmo_point"] = contains_point

        if goal_mask is None or mask_index is None:
            attempt["failure_reason"] = "no_selectable_mask"
            continue

        goal_bbox = _box_to_numpy(boxes[mask_index])
        metadata = {
            "langsam_queries": [item["query"] for item in attempts],
            "langsam_attempts": attempts,
            "langsam_selected_query": query,
            "langsam_selected_mask_index": mask_index,
            "langsam_mask_contains_point": contains_point,
            "langsam_failure_reason": None,
        }

        if segmentation_variant != "point_retry" or contains_point:
            return goal_mask, goal_bbox, metadata

        attempt["failure_reason"] = "mask_does_not_contain_molmo_point"
        if fallback is None:
            fallback = (goal_mask, goal_bbox)
            fallback_metadata = metadata

    if fallback is not None:
        fallback_metadata["langsam_failure_reason"] = "no_retry_mask_contained_molmo_point"
        return fallback[0], fallback[1], fallback_metadata

    raise Exception("LangSAM failed to segment the object.")


def get_prediction_result(
    image,
    path,
    scene_number,
    text,
    return_metadata=False,
    prompt_variant="legacy",
    model_name="qwen3.6-flash",
    max_output_tokens=64,
    mimo_retry_mode="none",
    segmentation_variant="baseline",
    evaluation_subset=None,
):
    if mimo_retry_mode not in VALID_MIMO_RETRY_MODES:
        raise ValueError(f"Unknown mimo_retry_mode: {mimo_retry_mode}")
    if segmentation_variant not in VALID_SEGMENTATION_VARIANTS:
        raise ValueError(f"Unknown segmentation_variant: {segmentation_variant}")

    reasoning = {
        "prompt_variant": prompt_variant,
        "model_name": model_name,
        "max_output_tokens": max_output_tokens,
        "mimo_retry_mode": mimo_retry_mode,
        "segmentation_variant": segmentation_variant,
        "evaluation_subset": evaluation_subset,
        "retry_count": 0,
        "raw_outputs": [],
        "failure_reason": None,
        "retry_reason": None,
    }

    try:
        scene_path = os.path.join(path)
        image_path = os.path.join(scene_path, f"{scene_number}.png")
        id_file_path = os.path.join(scene_path, f"{scene_number}_id.txt")

        image_pil = image 
        # image_pil = langsamutils.load_image(str(ori_image_path))
        
        # Load image as base64
        base64_image = load_image_as_base64(image_path)
        
        # Read object ID file
        parsed_data, molmo_to_gt_map, points_with_ids = parse_points_with_id(id_file_path)
        visible_object_ids = [item[0] for item in parsed_data]
        reasoning["visible_object_ids"] = visible_object_ids

        # GPT input text
        input_text = f"Grasp {text}"
        system_prompt = get_reasoning_system_prompt(prompt_variant)
        reasoning_input_text = _build_reasoning_input_text(input_text, parsed_data, prompt_variant)

        messages = _make_reasoning_messages(system_prompt, reasoning_input_text, base64_image)
        output = _call_reasoning_model(messages, model_name, max_output_tokens)
        reasoning["raw_outputs"].append(output)
        result = process_grasping_result(output, text)

        needs_id_repair = _needs_id_repair(result, visible_object_ids)
        needs_hard_review = mimo_retry_mode == "hard_review" and _is_hard_subset(evaluation_subset)
        needs_target_review = mimo_retry_mode == "target_review" and _is_hard_subset(evaluation_subset)
        needs_roborefer_verify = mimo_retry_mode == "roborefer_verify" and _is_hard_subset(evaluation_subset)
        needs_candidate_verify = mimo_retry_mode == "candidate_verify"
        needs_first_grasp_verify = mimo_retry_mode == "first_grasp_verify"
        if (
            mimo_retry_mode
            in {
                "id_repair",
                "hard_review",
                "target_review",
                "roborefer_verify",
                "candidate_verify",
                "first_grasp_verify",
            }
            and (
                needs_id_repair
                or needs_hard_review
                or needs_target_review
                or needs_roborefer_verify
                or needs_candidate_verify
                or needs_first_grasp_verify
            )
        ):
            initial_result = dict(result)
            initial_has_valid_id = not _needs_id_repair(initial_result, visible_object_ids)
            if needs_first_grasp_verify and not needs_id_repair:
                retry_reason = "first_grasp_verify"
                retry_text = _build_first_grasp_verify_text(input_text, parsed_data, output)
                if prompt_variant in {
                    "candidate_grasp_json",
                    "candidate_grasp_fewshot_json",
                    "candidate_grasp_spatial_json",
                }:
                    retry_system_prompt = get_reasoning_system_prompt(prompt_variant)
                else:
                    retry_system_prompt = get_reasoning_system_prompt("candidate_grasp_json")
            elif needs_candidate_verify and not needs_id_repair:
                retry_reason = "candidate_verify"
                retry_text = _build_candidate_verify_text(input_text, parsed_data, output)
                retry_system_prompt = get_reasoning_system_prompt("candidate_reasoning_json")
            elif needs_roborefer_verify and not needs_id_repair:
                retry_reason = "roborefer_verify"
                retry_text = _build_roborefer_verify_text(input_text, parsed_data, output)
                retry_system_prompt = get_reasoning_system_prompt("roborefer_json")
            elif needs_target_review and not needs_id_repair:
                retry_reason = "target_review"
                retry_text = _build_target_review_text(input_text, visible_object_ids, output)
                retry_system_prompt = get_reasoning_system_prompt("legacy")
            elif needs_hard_review:
                retry_reason = "hard_review"
                retry_text = _build_hard_review_text(input_text, visible_object_ids, output)
                retry_system_prompt = get_reasoning_system_prompt("hard_occlusion")
            else:
                retry_reason = "invalid_id"
                if prompt_variant in {
                    "roborefer_json",
                    "candidate_reasoning_json",
                    "candidate_grasp_json",
                    "candidate_grasp_fewshot_json",
                    "candidate_grasp_spatial_json",
                }:
                    if prompt_variant == "roborefer_json":
                        retry_text = _build_roborefer_id_repair_text(input_text, parsed_data, output)
                    elif prompt_variant in {
                        "candidate_grasp_json",
                        "candidate_grasp_fewshot_json",
                        "candidate_grasp_spatial_json",
                    }:
                        retry_text = _build_first_grasp_id_repair_text(input_text, parsed_data, output)
                    else:
                        retry_text = _build_candidate_id_repair_text(input_text, parsed_data, output)
                else:
                    retry_text = _build_id_repair_text(input_text, visible_object_ids, output)
                retry_system_prompt = system_prompt
            retry_messages = _make_reasoning_messages(retry_system_prompt, retry_text, base64_image)
            retry_output = _call_reasoning_model(retry_messages, model_name, max_output_tokens)
            reasoning["raw_outputs"].append(retry_output)
            reasoning["retry_count"] = 1
            reasoning["retry_reason"] = retry_reason
            retry_result = process_grasping_result(retry_output, text)
            retry_has_valid_id = not _needs_id_repair(retry_result, visible_object_ids)
            if retry_has_valid_id or not initial_has_valid_id:
                result = retry_result
            else:
                reasoning["retry_discarded"] = "invalid_retry_id"
                result = initial_result

        selected_object_id = result.get("selected_object_id")
        if (
            mimo_retry_mode
            in {
                "id_repair",
                "hard_review",
                "target_review",
                "roborefer_verify",
                "candidate_verify",
                "first_grasp_verify",
            }
            and selected_object_id is not None
            and selected_object_id not in visible_object_ids
        ):
            reasoning["invalid_selected_object_id"] = selected_object_id
            result.pop("selected_object_id", None)
            selected_object_id = None

        reasoning.update(
            {
                "raw_output": reasoning["raw_outputs"][-1] if reasoning["raw_outputs"] else "",
                "selected_object_id": selected_object_id,
                "class_name": result.get("class_name"),
                "mask_query": result.get("mask_query"),
                "reasoning_json": result.get("reasoning_json", {}),
                "selected_gt_id": molmo_to_gt_map.get(selected_object_id),
                "parse_status": "valid_id" if selected_object_id in visible_object_ids else "invalid_or_missing_id",
            }
        )

        if 'selected_object_id' not in result or result["selected_object_id"] not in visible_object_ids:
            print("No object id detected by GPT, using LangSAM for segmentation...")
            input2LangSAM = result.get("class_name", text)
            query_candidates = get_langsam_query_candidates(input2LangSAM, text)
            goal_mask, goal_bbox, segmentation_metadata = _predict_langsam_mask(
                image_pil,
                query_candidates if segmentation_variant == "point_retry" else query_candidates[:1],
                None,
                segmentation_variant,
            )
        else:
            goal = result.get("mask_query") or result["class_name"]
            goal_id = result['selected_object_id']
            goal_coor = get_coordinates(points_with_ids, goal_id)
            reasoning["molmo_point"] = list(goal_coor) if goal_coor is not None else None
            query_candidates = get_langsam_query_candidates(goal, text)
            goal_mask, goal_bbox, segmentation_metadata = _predict_langsam_mask(
                image_pil,
                query_candidates if segmentation_variant == "point_retry" else query_candidates[:1],
                goal_coor,
                segmentation_variant,
            )

        reasoning.update(segmentation_metadata)

        if return_metadata:
            return {"mask": goal_mask, "reasoning": reasoning_metadata}
        return goal_mask

    except Exception as e:
        if return_metadata:
            reasoning["failure_reason"] = str(e)
            return {
                "error": str(e),
                "reasoning": reasoning,
            }
        return {"error": str(e)}
