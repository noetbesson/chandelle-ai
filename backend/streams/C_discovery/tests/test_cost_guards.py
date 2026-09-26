"""Tests hors ligne : chaque client OpenAI est remplacé avant exécution."""

import importlib
import io
import json
import os
from contextlib import redirect_stdout, redirect_stderr
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.streams.C_discovery import data, run_discovery as runner
from backend.streams.C_discovery.sources import openai_web
from backend.streams.C_discovery.normalizers.models import SearchResults


class CostGuards(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        dotenv = patch.object(runner, "load_dotenv")
        dotenv.start()
        self.addCleanup(dotenv.stop)
        client = patch.object(runner, "OpenAI")
        self.client = client.start()
        self.addCleanup(client.stop)
        argv = patch("sys.argv", ["discovery"])
        argv.start()
        self.addCleanup(argv.stop)

    def run_main(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = runner.main()
        return code, output.getvalue()

    def test_live_requires_exact_true_before_client_creation(self):
        for value in ("", "false", "True", "1", " true "):
            with self.subTest(value=value):
                os.environ["DISCOVERY_ENABLE_LIVE"] = value
                code, output = self.run_main()
                self.assertEqual(code, 0)
                self.assertEqual(output.strip(), "Live discovery disabled: no OpenAI API call made.")
        self.client.assert_not_called()

    def test_bad_limits_and_missing_key_make_no_call(self):
        os.environ["DISCOVERY_ENABLE_LIVE"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-only"
        for value in ("0", "6", "25", "abc", ""):
            os.environ["DISCOVERY_LIMIT"] = value
            self.assertEqual(self.run_main()[0], 1)
        os.environ["DISCOVERY_LIMIT"] = "5"
        with patch("sys.argv", ["discovery", "--limit", "6"]):
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                runner.main()
        del os.environ["OPENAI_API_KEY"]
        self.assertEqual(self.run_main()[0], 1)
        self.client.assert_not_called()

    def test_one_request_even_for_invalid_result_and_usage_is_reported(self):
        os.environ.update(DISCOVERY_ENABLE_LIVE="true", OPENAI_API_KEY="test-only", DISCOVERY_LIMIT="3")
        response = SimpleNamespace(
            id="resp_test", usage=Mock(), status="completed",
            output_text=json.dumps({"activities": []}),
            model_dump=lambda **kwargs: {"output": [{"type": "web_search_call", "status": "completed"}]},
        )
        response.usage.model_dump.return_value = {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}
        create = self.client.return_value.__enter__.return_value.responses.create
        create.return_value = response
        with TemporaryDirectory() as temp, patch.object(runner, "STREAM_DIR", Path(temp)):
            code, output = self.run_main()
            self.assertEqual(code, 1)
            self.assertFalse((Path(temp) / "data/activities.json").exists())
        create.assert_called_once()
        self.assertEqual(self.client.call_args.kwargs["max_retries"], 0)
        request = create.call_args.kwargs
        self.assertEqual(request["tools"], [{"type": "web_search"}])
        self.assertEqual(request["max_tool_calls"], 1)
        self.assertEqual(request["max_output_tokens"], 3500)
        for text in ("Activités demandées : 3", "Activités retournées : 0", "resp_test", '"total_tokens": 110'):
            self.assertIn(text, output)

    def test_source_cannot_bypass_disabled_flag_or_limit(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            openai_web.search_activities(client, schema={}, today=date.today())
        os.environ["DISCOVERY_ENABLE_LIVE"] = "true"
        with self.assertRaises(ValueError):
            openai_web.search_activities(client, schema={}, today=date.today(), limit=6)
        client.responses.create.assert_not_called()

    def test_api_schema_limits_results_and_keeps_url_validation_local(self):
        schema = openai_web.api_schema(SearchResults.model_json_schema(), 5)
        self.assertEqual(schema["properties"]["activities"]["maxItems"], 5)
        self.assertNotIn('"format": "uri"', json.dumps(schema))

    def test_missing_sources_metadata_does_not_crash(self):
        self.assertEqual(runner.source_urls({"output": [
            {"type": "web_search_call", "action": {"sources": None}},
            {"type": "message", "content": [{"annotations": None}]},
        ]}), set())

    def test_connection_failure_does_not_trigger_another_request(self):
        os.environ.update(DISCOVERY_ENABLE_LIVE="true", OPENAI_API_KEY="test-only")
        create = self.client.return_value.__enter__.return_value.responses.create
        create.side_effect = runner.APIConnectionError(request=Mock())
        code, output = self.run_main()
        self.assertEqual(code, 1)
        create.assert_called_once()
        self.assertIn("retournées : indisponible", output)

    def test_import_and_local_reader_never_create_client(self):
        os.environ.update(DISCOVERY_ENABLE_LIVE="true", OPENAI_API_KEY="test-only")
        with patch("openai.OpenAI") as client:
            importlib.reload(openai_web)
            importlib.reload(runner)
            with TemporaryDirectory() as temp, patch.object(data, "__file__", str(Path(temp) / "__init__.py")):
                with self.assertRaises(FileNotFoundError):
                    data.load_activities()
                (Path(temp) / "activities.json").write_text("[]")
                self.assertEqual(data.load_activities(), [])
            client.assert_not_called()
