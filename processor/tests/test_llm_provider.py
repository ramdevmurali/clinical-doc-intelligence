import json
import unittest
from unittest.mock import patch

from processor.src.domain.ai_extraction_prompt import PromptMessage
from processor.src.domain.ai_extraction_response import AI_EXTRACTION_RESPONSE_SCHEMA_VERSION
from processor.src.services.llm_provider import (
    FixtureLlmProvider,
    GeminiGenerateContentProvider,
    LlmProviderError,
    provider_for_name,
)


class LlmProviderTests(unittest.TestCase):
    def test_fixture_provider_returns_empty_candidate_response_by_document_id(self) -> None:
        provider = FixtureLlmProvider()

        response = provider.complete_json(
            model="fixture-model",
            messages=(PromptMessage(role="user", content="Document ID: note_test"),),
            timeout_seconds=1,
        )

        self.assertEqual("fixture", response.provider)
        self.assertEqual("fixture-model", response.model)
        self.assertEqual("fixture:note_test", response.request_id)
        self.assertEqual(
            {
                "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
                "document_id": "note_test",
                "items": [],
            },
            json.loads(response.content),
        )

    def test_provider_for_name_gemini_requires_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(LlmProviderError, "GEMINI_API_KEY"):
                provider_for_name("gemini")

    def test_provider_for_name_gemini_reads_api_key_from_environment(self) -> None:
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True):
            provider = provider_for_name("gemini")

        self.assertIsInstance(provider, GeminiGenerateContentProvider)

    def test_provider_for_name_gemini_accepts_google_api_key_fallback(self) -> None:
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=True):
            provider = provider_for_name("gemini")

        self.assertIsInstance(provider, GeminiGenerateContentProvider)

    def test_gemini_provider_posts_generate_content_request_and_extracts_output_text(self) -> None:
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            return FakeHttpResponse(
                {
                    "responseId": "gemini-response-123",
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
                                                "document_id": "note_test",
                                                "items": [],
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 11,
                        "candidatesTokenCount": 7,
                    },
                }
            )

        provider = GeminiGenerateContentProvider(
            api_key="test-key",
            endpoint="https://example.test/v1beta",
            urlopen_func=fake_urlopen,
        )

        response = provider.complete_json(
            model="gemini-test",
            messages=(
                PromptMessage(role="system", content="extract only"),
                PromptMessage(role="user", content="Document ID: note_test"),
            ),
            timeout_seconds=12.5,
        )

        self.assertEqual("gemini", response.provider)
        self.assertEqual("gemini-test", response.model)
        self.assertEqual("gemini-response-123", response.request_id)
        self.assertEqual(11, response.input_tokens)
        self.assertEqual(7, response.output_tokens)
        self.assertEqual(
            {
                "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
                "document_id": "note_test",
                "items": [],
            },
            json.loads(response.content),
        )

        self.assertEqual(1, len(calls))
        request, timeout = calls[0]
        self.assertEqual(12.5, timeout)
        self.assertEqual(
            "https://example.test/v1beta/models/gemini-test:generateContent?key=test-key",
            request.full_url,
        )
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(0, request_body["generationConfig"]["temperature"])
        self.assertEqual("application/json", request_body["generationConfig"]["responseMimeType"])
        self.assertEqual("OBJECT", request_body["generationConfig"]["responseSchema"]["type"])
        self.assertEqual("extract only", request_body["systemInstruction"]["parts"][0]["text"])
        self.assertEqual("user", request_body["contents"][0]["role"])
        self.assertEqual("Document ID: note_test", request_body["contents"][0]["parts"][0]["text"])

    def test_gemini_provider_joins_multiple_text_parts(self) -> None:
        def fake_urlopen(request, timeout):
            return FakeHttpResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": (
                                            '{"schema_version":"'
                                            f'{AI_EXTRACTION_RESPONSE_SCHEMA_VERSION}",'
                                        )
                                    },
                                    {"text": '"document_id":"note_test","items":[]}'},
                                ]
                            }
                        }
                    ]
                }
            )

        provider = GeminiGenerateContentProvider(api_key="test-key", urlopen_func=fake_urlopen)

        response = provider.complete_json(
            model="gemini-test",
            messages=(PromptMessage(role="user", content="Document ID: note_test"),),
            timeout_seconds=1,
        )

        self.assertEqual("note_test", json.loads(response.content)["document_id"])

    def test_gemini_provider_rejects_response_without_output_text(self) -> None:
        def fake_urlopen(request, timeout):
            return FakeHttpResponse({"responseId": "gemini-response-123", "candidates": []})

        provider = GeminiGenerateContentProvider(api_key="test-key", urlopen_func=fake_urlopen)

        with self.assertRaisesRegex(LlmProviderError, "output text"):
            provider.complete_json(
                model="gemini-test",
                messages=(PromptMessage(role="user", content="Document ID: note_test"),),
                timeout_seconds=1,
            )


class FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
