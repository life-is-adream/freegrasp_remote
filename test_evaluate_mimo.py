import os
import unittest
from unittest.mock import patch

import evaluate_mimo


class FakeResponse:
    status_code = 200
    text = '{"choices":[{"message":{"content":"[1, red box]"}}]}'

    def json(self):
        return {"choices": [{"message": {"content": "[1, red box]"}}]}

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or FakeResponse()

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


class FakeImageUnsupportedResponse:
    status_code = 404
    text = '{"error":{"message":"No endpoints found that support image input"}}'

    def json(self):
        return {"error": {"message": "No endpoints found that support image input"}}


class EvaluateMimoClientTest(unittest.TestCase):
    def test_create_mimo_client_ignores_socks_proxy_environment(self):
        fake_http = FakeHttpClient()

        with patch.dict(os.environ, {"ALL_PROXY": "socks5://127.0.0.1:7890"}, clear=False):
            client = evaluate_mimo.create_mimo_client(
                api_key="test-key",
                base_url="https://example.test/v1",
                http_client=fake_http,
            )

        self.assertIsNone(os.environ.get("ALL_PROXY"))
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.base_url, "https://example.test/v1")

    def test_tp_key_defaults_to_token_plan_base_url(self):
        fake_http = FakeHttpClient()

        with patch.dict(os.environ, {"MIMO_API_KEY": "tp-test"}, clear=True):
            client = evaluate_mimo.create_mimo_client(http_client=fake_http)

        self.assertEqual(client.base_url, "https://token-plan-cn.xiaomimimo.com/v1")

    def test_chat_completion_uses_mimo_token_plan_wire_format(self):
        fake_http = FakeHttpClient()
        client = evaluate_mimo.create_mimo_client(
            api_key="tp-test",
            base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            http_client=fake_http,
        )

        response = client.chat.completions.create(
            model="mimo-v2.5",
            messages=[{"role": "user", "content": "hello"}],
            temperature=0,
            max_tokens=713,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            seed=0,
        )

        self.assertEqual(response.choices[0].message.content, "[1, red box]")
        call = fake_http.calls[0]
        self.assertEqual(call["url"], "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions")
        self.assertEqual(call["headers"]["api-key"], "tp-test")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertEqual(call["json"]["model"], "mimo-v2.5")
        self.assertEqual(call["json"]["max_completion_tokens"], 713)
        self.assertEqual(call["json"]["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn("max_tokens", call["json"])
        self.assertNotIn("frequency_penalty", call["json"])
        self.assertNotIn("presence_penalty", call["json"])
        self.assertNotIn("seed", call["json"])

    def test_explicit_chat_template_kwargs_are_preserved(self):
        fake_http = FakeHttpClient()
        client = evaluate_mimo.create_mimo_client(
            api_key="tp-test",
            base_url="https://token-plan-cn.xiaomimimo.com/v1",
            http_client=fake_http,
        )

        client.chat.completions.create(
            model="mimo-v2.5",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=8,
            chat_template_kwargs={"enable_thinking": True},
        )

        self.assertEqual(fake_http.calls[0]["json"]["chat_template_kwargs"], {"enable_thinking": True})

    def test_validate_image_input_support_fails_fast_for_unsupported_model(self):
        fake_http = FakeHttpClient(response=FakeImageUnsupportedResponse())
        client = evaluate_mimo.create_mimo_client(
            api_key="tp-test",
            base_url="https://token-plan-cn.xiaomimimo.com/v1",
            http_client=fake_http,
        )

        with self.assertRaisesRegex(RuntimeError, "does not support image input"):
            evaluate_mimo.validate_mimo_supports_image_input(client, "mimo-v2.5-pro")

    def test_parse_args_exposes_boost_ablation_switches(self):
        args = evaluate_mimo.parse_args(
            [
                "--model-name",
                "mimo-v2.5",
                "--prompt-variant",
                "hard_occlusion",
                "--mimo-retry-mode",
                "hard_review",
                "--segmentation-variant",
                "point_retry",
                "--subset-policy",
                "easy_direct_hard_occlusion_v1",
            ]
        )

        self.assertEqual(args.prompt_variant, "hard_occlusion")
        self.assertEqual(args.mimo_retry_mode, "hard_review")
        self.assertEqual(args.segmentation_variant, "point_retry")
        self.assertEqual(args.subset_policy, "easy_direct_hard_occlusion_v1")

    def test_parse_args_accepts_best_known_subset_policy(self):
        args = evaluate_mimo.parse_args(["--subset-policy", "best_known_v1"])

        self.assertEqual(args.subset_policy, "best_known_v1")

    def test_parse_args_accepts_target_review_and_best_known_v2(self):
        args = evaluate_mimo.parse_args(
            [
                "--mimo-retry-mode",
                "target_review",
                "--subset-policy",
                "best_known_v2",
            ]
        )

        self.assertEqual(args.mimo_retry_mode, "target_review")
        self.assertEqual(args.subset_policy, "best_known_v2")

    def test_parse_args_accepts_roborefer_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "roborefer_json",
                "--mimo-retry-mode",
                "roborefer_verify",
                "--subset-policy",
                "roborefer_v1",
            ]
        )

        self.assertEqual(args.prompt_variant, "roborefer_json")
        self.assertEqual(args.mimo_retry_mode, "roborefer_verify")
        self.assertEqual(args.subset_policy, "roborefer_v1")

    def test_parse_args_accepts_light_review_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "visible_id_guard",
                "--mimo-retry-mode",
                "target_review",
                "--subset-policy",
                "light_review_v1",
            ]
        )

        self.assertEqual(args.prompt_variant, "visible_id_guard")
        self.assertEqual(args.mimo_retry_mode, "target_review")
        self.assertEqual(args.subset_policy, "light_review_v1")

    def test_parse_args_accepts_candidate_grasp_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "candidate_grasp_json",
                "--mimo-retry-mode",
                "first_grasp_verify",
                "--subset-policy",
                "candidate_grasp_v2",
            ]
        )

        self.assertEqual(args.prompt_variant, "candidate_grasp_json")
        self.assertEqual(args.mimo_retry_mode, "first_grasp_verify")
        self.assertEqual(args.subset_policy, "candidate_grasp_v2")

    def test_parse_args_accepts_candidate_grasp_fewshot_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "candidate_grasp_fewshot_json",
                "--mimo-retry-mode",
                "first_grasp_verify",
                "--subset-policy",
                "candidate_grasp_fewshot_v3",
            ]
        )

        self.assertEqual(args.prompt_variant, "candidate_grasp_fewshot_json")
        self.assertEqual(args.mimo_retry_mode, "first_grasp_verify")
        self.assertEqual(args.subset_policy, "candidate_grasp_fewshot_v3")

    def test_parse_args_accepts_candidate_grasp_spatial_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "candidate_grasp_spatial_json",
                "--mimo-retry-mode",
                "first_grasp_verify",
                "--subset-policy",
                "candidate_grasp_spatial_v4",
            ]
        )

        self.assertEqual(args.prompt_variant, "candidate_grasp_spatial_json")
        self.assertEqual(args.mimo_retry_mode, "first_grasp_verify")
        self.assertEqual(args.subset_policy, "candidate_grasp_spatial_v4")

    def test_parse_args_accepts_candidate_grasp_semantic_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "candidate_grasp_semantic_json",
                "--mimo-retry-mode",
                "first_grasp_verify",
                "--subset-policy",
                "candidate_grasp_semantic_v5",
            ]
        )

        self.assertEqual(args.prompt_variant, "candidate_grasp_semantic_json")
        self.assertEqual(args.mimo_retry_mode, "first_grasp_verify")
        self.assertEqual(args.subset_policy, "candidate_grasp_semantic_v5")

    def test_parse_args_accepts_target_first_grasp_planner_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "target_first_grasp_planner_json",
                "--mimo-retry-mode",
                "first_grasp_verify",
                "--subset-policy",
                "target_first_grasp_planner_v6",
            ]
        )

        self.assertEqual(args.prompt_variant, "target_first_grasp_planner_json")
        self.assertEqual(args.mimo_retry_mode, "first_grasp_verify")
        self.assertEqual(args.subset_policy, "target_first_grasp_planner_v6")

    def test_parse_args_accepts_target_first_grasp_planner_v7_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "target_first_grasp_planner_v7_json",
                "--mimo-retry-mode",
                "planner_consistency_repair",
                "--subset-policy",
                "target_first_grasp_planner_v7",
            ]
        )

        self.assertEqual(args.prompt_variant, "target_first_grasp_planner_v7_json")
        self.assertEqual(args.mimo_retry_mode, "planner_consistency_repair")
        self.assertEqual(args.subset_policy, "target_first_grasp_planner_v7")

    def test_parse_args_accepts_target_first_grasp_geometry_v8_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "target_first_grasp_geometry_v8_json",
                "--mimo-retry-mode",
                "geometry_consistency_repair",
                "--subset-policy",
                "target_first_grasp_geometry_v8",
            ]
        )

        self.assertEqual(args.prompt_variant, "target_first_grasp_geometry_v8_json")
        self.assertEqual(args.mimo_retry_mode, "geometry_consistency_repair")
        self.assertEqual(args.subset_policy, "target_first_grasp_geometry_v8")

    def test_parse_args_accepts_target_first_evidence_gate_v9_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "target_first_evidence_gate_v9_json",
                "--mimo-retry-mode",
                "geometry_consistency_repair",
                "--subset-policy",
                "target_first_evidence_gate_v9",
            ]
        )

        self.assertEqual(args.prompt_variant, "target_first_evidence_gate_v9_json")
        self.assertEqual(args.mimo_retry_mode, "geometry_consistency_repair")
        self.assertEqual(args.subset_policy, "target_first_evidence_gate_v9")

    def test_parse_args_accepts_hard_blocker_first_v10_hooks(self):
        args = evaluate_mimo.parse_args(
            [
                "--prompt-variant",
                "hard_blocker_first_v10_json",
                "--mimo-retry-mode",
                "id_repair",
                "--subset-policy",
                "hard_blocker_first_v10",
            ]
        )

        self.assertEqual(args.prompt_variant, "hard_blocker_first_v10_json")
        self.assertEqual(args.mimo_retry_mode, "id_repair")
        self.assertEqual(args.subset_policy, "hard_blocker_first_v10")


if __name__ == "__main__":
    unittest.main()
