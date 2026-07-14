import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autodoc.ai.copilot import (
    CopilotAIProvider,
    _build_screenshot_attachments,
    _build_test_evidence_prompt,
    _clean_comment_response,
)


class CopilotEvidenceCommentTests(unittest.TestCase):
    def test_prompt_supports_generate_mode_and_includes_all_context(self):
        prompt = _build_test_evidence_prompt(
            mode="Generate",
            test_scenario="User logs in with valid credentials",
            expected_result="Dashboard is displayed",
            test_data="user=test@example.com",
            existing_comment="",
            previous_comments=["Login page opened", "Credentials entered"],
            has_screenshot=True,
        )

        self.assertIn("Generate a new professional test-evidence comment.", prompt)
        self.assertIn("Return exactly one short sentence on one line", prompt)
        self.assertIn("Do not list files, folders, timestamps", prompt)
        self.assertIn("<mode>generate</mode>", prompt)
        self.assertIn("<test_scenario>User logs in with valid credentials</test_scenario>", prompt)
        self.assertIn("1. Login page opened", prompt)
        self.assertIn("Use the attached screenshot", prompt)

    def test_prompt_supports_rewrite_mode(self):
        prompt = _build_test_evidence_prompt(
            mode="rewrite",
            test_scenario="Submit order",
            expected_result="Order confirmation appears",
            test_data=None,
            existing_comment="ok",
            previous_comments=None,
            has_screenshot=False,
        )

        self.assertIn("Rewrite the existing comment", prompt)
        self.assertIn("<existing_comment>ok</existing_comment>", prompt)
        self.assertIn("No screenshot is attached.", prompt)

    def test_prompt_instructs_description_rewrite_and_technical_correction(self):
        prompt = _build_test_evidence_prompt(
            mode="generate",
            test_scenario="Open SAP transaction",
            expected_result="Transaction screen is displayed",
            test_data="T-code VA01",
            existing_comment=None,
            previous_comments=None,
            has_screenshot=True,
        )

        self.assertIn("Describe what is visible in the screenshot", prompt)
        self.assertIn("rewrite the existing text with correct grammar", prompt)
        self.assertIn("SAP transaction codes or table names", prompt)
        self.assertIn("provide a brief explanation", prompt)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            _build_test_evidence_prompt(
                mode="summarize",
                test_scenario="Scenario",
                expected_result="Expected",
                test_data=None,
                existing_comment=None,
                previous_comments=None,
                has_screenshot=False,
            )

    def test_screenshot_bytes_use_blob_attachment(self):
        attachments = _build_screenshot_attachments(
            screenshot_path=None,
            screenshot_bytes=b"abc",
            screenshot_mime_type="image/png",
        )

        self.assertEqual(attachments[0]["type"], "blob")
        self.assertEqual(attachments[0]["mimeType"], "image/png")
        self.assertEqual(attachments[0]["data"], "YWJj")

    def test_screenshot_path_uses_absolute_file_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "evidence.png"
            screenshot.write_bytes(b"not-a-real-png")

            attachments = _build_screenshot_attachments(
                screenshot_path=screenshot,
                screenshot_bytes=None,
                screenshot_mime_type=None,
            )

        self.assertEqual(attachments[0]["type"], "file")
        self.assertTrue(Path(attachments[0]["path"]).is_absolute())
        self.assertEqual(attachments[0]["displayName"], "evidence.png")

    def test_clean_comment_response_removes_common_wrappers(self):
        self.assertEqual(
            _clean_comment_response('```text\nComment: "The dashboard was displayed successfully."\n```'),
            "The dashboard was displayed successfully.",
        )

    def test_clean_comment_response_keeps_only_one_short_line(self):
        response = (
            "Screenshot captured the AutoDoc directory on drive K: showing repository structure and files. "
            "Visible items included folders and scripts with timestamps."
        )

        self.assertEqual(
            _clean_comment_response(response),
            "Screenshot captured the AutoDoc directory on drive K: showing repository structure and files.",
        )

    def test_empty_env_tokens_fall_back_to_logged_in_user(self):
        with patch.dict(
            os.environ,
            {"COPILOT_GITHUB_TOKEN": "", "GH_TOKEN": "", "GITHUB_TOKEN": ""},
            clear=False,
        ):
            provider = CopilotAIProvider.from_env()

        self.assertIsNone(provider.github_token)
        self.assertTrue(provider.use_logged_in_user)


if __name__ == "__main__":
    unittest.main()
