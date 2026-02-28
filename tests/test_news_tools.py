from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_crew.tools.news_tools import CompanyNewsSearchTool  # noqa: E402


class NewsToolsTests(TestCase):
    def test_parse_dockermcp_json_with_prefix(self):
        raw = 'Tool call took: 6.39s\n{"results":[{"title":"A"}]}'
        parsed = CompanyNewsSearchTool._parse_dockermcp_json(raw)
        self.assertEqual(parsed["results"][0]["title"], "A")

    def test_normalize_results_maps_published_date_variants(self):
        tool = CompanyNewsSearchTool()
        normalized = tool._normalize_results(
            {
                "results": [
                    {
                        "title": "Morgan Stanley update",
                        "url": "https://example.com/news",
                        "publishedDate": "2026-02-28T00:00:00.000Z",
                        "summary": "News summary",
                    }
                ]
            }
        )

        self.assertEqual(normalized[0]["published_date"], "2026-02-28T00:00:00.000Z")
        self.assertEqual(normalized[0]["url"], "https://example.com/news")

    @patch.dict(os.environ, {"EXA_API_KEY": ""}, clear=False)
    @patch("automation_crew.tools.news_tools.CompanyNewsSearchTool._run_dockermcp_exa_search")
    def test_sparse_priority_results_trigger_fallback_with_medium_confidence(
        self, mock_dockermcp_search
    ):
        mock_dockermcp_search.side_effect = [
            [
                {
                    "title": "Priority source story",
                    "url": "https://reuters.com/priority",
                    "published_date": "2026-02-20",
                    "summary": "Priority result",
                }
            ],
            [
                {
                    "title": "Broad source story",
                    "url": "https://example.com/broad",
                    "published_date": "2026-02-21",
                    "summary": "Broad result",
                }
            ],
        ]

        output = json.loads(
            CompanyNewsSearchTool()._run("MS", "Morgan Stanley", lookback_days=30)
        )

        self.assertTrue(output["fallback_used"])
        self.assertEqual(output["source_confidence"], "medium")
        self.assertEqual(output["total_results_count"], 2)
        self.assertEqual(output["news_backend"], "dockermcp_exa_tool")
        self.assertGreaterEqual(mock_dockermcp_search.call_count, 2)

    @patch.dict(os.environ, {"EXA_API_KEY": ""}, clear=False)
    @patch("automation_crew.tools.news_tools.CompanyNewsSearchTool._run_dockermcp_exa_search")
    def test_empty_results_set_low_confidence_and_quality_note(
        self, mock_dockermcp_search
    ):
        mock_dockermcp_search.side_effect = [[], []]

        output = json.loads(
            CompanyNewsSearchTool()._run("MS", "Morgan Stanley", lookback_days=30)
        )

        self.assertTrue(output["fallback_used"])
        self.assertEqual(output["source_confidence"], "low")
        self.assertEqual(output["total_results_count"], 0)
        notes = output["data_quality_notes"]
        self.assertTrue(
            any("No recent news articles were returned by Exa." in note for note in notes)
        )

    @patch("automation_crew.tools.news_tools.subprocess.run")
    def test_dockermcp_cli_error_raises_runtime_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "mcp", "tools", "call", "web_search_exa"],
            stderr="permission denied",
        )

        with self.assertRaises(RuntimeError) as exc:
            CompanyNewsSearchTool()._run_dockermcp_exa_search("Morgan Stanley latest")

        message = str(exc.exception)
        self.assertIn("DockerMCP Exa search failed", message)
        self.assertIn("permission denied", message)

    @patch.dict(os.environ, {"EXA_API_KEY": ""}, clear=False)
    @patch("automation_crew.tools.news_tools.CompanyNewsSearchTool._run_dockermcp_exa_search")
    def test_india_market_uses_india_priority_domains(self, mock_dockermcp_search):
        mock_dockermcp_search.side_effect = [[], []]

        output = json.loads(
            CompanyNewsSearchTool()._run(
                "RELIANCE",
                "Reliance Industries",
                lookback_days=14,
                market="india",
            )
        )

        self.assertEqual(output["market"], "india")
        self.assertIn("moneycontrol.com", output["priority_domains"])
        self.assertIn("economictimes.indiatimes.com", output["priority_domains"])
