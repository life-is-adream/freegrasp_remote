import json


def _load_results(results_or_path):
    if isinstance(results_or_path, (str, bytes)):
        with open(results_or_path, "r") as f:
            return json.load(f)
    try:
        with open(results_or_path, "r") as f:
            return json.load(f)
    except TypeError:
        return results_or_path


def calculate_accuracy(output_json_path):
    results = _load_results(output_json_path)
    
    # Calculate total number of samples and correct prediction
    total_samples = len(results)
    correct_predictions = sum(1 for item in results if item[3] == 1)
    
    # Calculate accuracy
    accuracy = correct_predictions / total_samples if total_samples > 0 else 0
    
    print(f"Total Samples: {total_samples}")
    print(f"Correct Predictions: {correct_predictions}")
    print(f"Accuracy: {accuracy:.2%}")
    
    return accuracy


def calculate_reasoning_accuracy(results_or_path):
    results = _load_results(results_or_path)

    total_samples = len(results)
    correct_predictions = sum(1 for item in results if len(item) > 4 and item[4] == 1)
    accuracy = correct_predictions / total_samples if total_samples > 0 else 0

    print(f"Total Samples: {total_samples}")
    print(f"Correct Reasoning Predictions: {correct_predictions}")
    print(f"RSR Accuracy: {accuracy:.2%}")

    return accuracy

if __name__ == "__main__":
    # Example
    output_json_path = "data/output/out_easy_no_ambi.json"
    sr = calculate_accuracy(output_json_path)
