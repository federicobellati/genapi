import os
import unittest
from unittest.mock import MagicMock, patch
import requests
from fastapi.testclient import TestClient
from main import app


@patch.dict(os.environ, {"HERMES_API_KEY": "test-only-key"})
class AlviseGraphTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.question = "What is the Impact of surface waves on ocean circulation?"

    @patch("alvise_graph.requests.post")
    def test_question_only_activates_fixed_graph_and_returns_markdown(self, post):
        answer = "EXTRACTED: Wave effects. Source: waves.md"
        post.return_value.json.return_value = {"choices": [{"message": {"content": answer}, "finish_reason": "stop"}]}
        response = self.client.post("/alvise-graph/query", json={"question": f"  {self.question}  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, answer)
        self.assertTrue(response.headers["content-type"].startswith("text/markdown"))
        self.assertIn('filename="answer.md"', response.headers["content-disposition"])
        post.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user"])
        self.assertTrue(payload["messages"][1]["content"].startswith(f"graphify query: {self.question}\n"))
        for message in payload["messages"]:
            for rule in ("/opt/data/home/alvise_benetazzo_articles_MD/graphify-out/", "nodes, hyperedges, communities", "Do not use external knowledge", "EXTRACTED or INFERRED", ".md", "Not found in the Alvise Benettazzo corpus"):
                self.assertIn(rule, message["content"])
        self.assertNotIn("test-only-key", response.text)
        self.assertNotIn("session_id", payload)

    @patch("alvise_graph.requests.post")
    def test_invalid_input_and_client_overrides_never_reach_hermes(self, post):
        for body in ({}, {"question": ""}, {"question": " \n "}, {"question": 123}, {"question": None}, {"question": "x" * 4001}, *({"question": self.question, field: "override"} for field in ("graph", "prompt", "model", "session_id", "instructions"))):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/alvise-graph/query", json=body).status_code, 422)
        post.assert_not_called()

    @patch("alvise_graph.requests.post")
    def test_missing_key_does_not_contact_hermes(self, post):
        with patch.dict(os.environ, {"HERMES_API_KEY": " "}):
            self.assertEqual(self.client.post("/alvise-graph/query", json={"question": self.question}).status_code, 503)
        post.assert_not_called()

    @patch("alvise_graph.requests.post")
    def test_hermes_errors_are_reported_without_retries_or_secrets(self, post):
        for error, status in ((requests.Timeout("test-only-key"), 504), (requests.ConnectionError("test-only-key"), 502), (requests.HTTPError("test-only-key"), 502)):
            with self.subTest(error=type(error).__name__):
                post.reset_mock()
                post.side_effect = error
                response = self.client.post("/alvise-graph/query", json={"question": self.question})
                self.assertEqual(response.status_code, status)
                self.assertNotIn("test-only-key", response.text)
                post.assert_called_once()

    @patch("alvise_graph.requests.post")
    def test_empty_malformed_or_incomplete_answers_are_not_successes(self, post):
        for result in ({"choices": []}, {"choices": [{}]}, None, *({"choices": [{"message": {"content": content}, "finish_reason": reason}]} for content, reason in ((None, "stop"), (" ", "stop"), ("Partial", "length"), ("Error", "error"), ("Tool call", "tool_calls")))):
            with self.subTest(result=result):
                post.return_value = MagicMock()
                post.return_value.json.return_value = result
                self.assertEqual(self.client.post("/alvise-graph/query", json={"question": self.question}).status_code, 502)
        post.return_value.json.side_effect = ValueError("invalid JSON")
        self.assertEqual(self.client.post("/alvise-graph/query", json={"question": self.question}).status_code, 502)

    def test_cors_and_openapi_include_new_endpoint(self):
        response = self.client.options("/alvise-graph/query", headers={"Origin": "https://assets.ve.ismar.cnr.it", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://assets.ve.ismar.cnr.it")
        self.assertIn("text/markdown", self.client.get("/openapi.json").json()["paths"]["/alvise-graph/query"]["post"]["responses"]["200"]["content"])
