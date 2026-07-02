import importlib.util
import types
import unittest
from pathlib import Path

import torch


def load_ms_deform_attn():
    module_path = (
        Path(__file__).resolve().parent
        / "models/langsam/GroundingDINO/groundingdino/models/GroundingDINO/ms_deform_attn.py"
    )
    spec = importlib.util.spec_from_file_location("freegrasp_ms_deform_attn", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MultiScaleDeformableAttentionCompatibilityTest(unittest.TestCase):
    def test_missing_custom_op_uses_python_fallback_even_for_cuda_tensor(self):
        module = load_ms_deform_attn()
        module._C = None
        fake_cuda_value = types.SimpleNamespace(is_cuda=True)
        original_is_available = torch.cuda.is_available
        torch.cuda.is_available = lambda: True
        try:
            self.assertFalse(module._should_use_custom_ms_deform_attn(fake_cuda_value))
        finally:
            torch.cuda.is_available = original_is_available


if __name__ == "__main__":
    unittest.main()
