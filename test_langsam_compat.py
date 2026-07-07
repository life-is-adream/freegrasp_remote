import types
import unittest
import importlib.util
from pathlib import Path

import torch
from torch import nn


def load_bert_model_warper():
    module_path = (
        Path(__file__).resolve().parent
        / "models/langsam/GroundingDINO/groundingdino/models/GroundingDINO/bertwarper.py"
    )
    spec = importlib.util.spec_from_file_location("freegrasp_bertwarper", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BertModelWarper


class DummyBertWithoutHeadMask(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = types.SimpleNamespace(
            is_decoder=False,
            output_attentions=False,
            output_hidden_states=False,
            use_return_dict=True,
            num_hidden_layers=2,
        )
        self.embeddings = nn.Identity()
        self.encoder = nn.Identity()
        self.pooler = None
        self.received_attention_mask_dtype = None
        self.invert_attention_mask = lambda *args, **kwargs: None

    def get_extended_attention_mask(self, attention_mask, input_shape, dtype=None):
        self.received_attention_mask_dtype = dtype
        return attention_mask.to(dtype=dtype)


class LangSAMCompatibilityTest(unittest.TestCase):
    def test_bert_model_warper_supports_transformers_without_get_head_mask(self):
        BertModelWarper = load_bert_model_warper()
        warper = BertModelWarper(DummyBertWithoutHeadMask())

        self.assertEqual(warper.get_head_mask(None, 2), [None, None])

    def test_extended_attention_mask_uses_dtype_not_device_for_new_transformers(self):
        BertModelWarper = load_bert_model_warper()
        dummy = DummyBertWithoutHeadMask()
        warper = BertModelWarper(dummy)

        mask = torch.ones((1, 2), dtype=torch.long)
        result = warper.get_extended_attention_mask(mask, (1, 2), torch.device("cpu"))

        self.assertEqual(dummy.received_attention_mask_dtype, torch.float32)
        self.assertEqual(result.dtype, torch.float32)

    def test_bert_model_reference_is_not_registered_as_extra_submodule(self):
        BertModelWarper = load_bert_model_warper()
        warper = BertModelWarper(DummyBertWithoutHeadMask())

        self.assertNotIn("_bert_model", dict(warper.named_children()))


if __name__ == "__main__":
    unittest.main()
