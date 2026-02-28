from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_crew.crew import AutomationCrew  # noqa: E402


class CrewStructureTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "OPENROUTER_MODEL": "openrouter/free-model",
            "OPENROUTER_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_parallel_task_graph_and_contexts(self):
        crew_instance = AutomationCrew()

        news_task = crew_instance.get_company_news()
        financial_task = crew_instance.get_company_financials()
        analysis_task = crew_instance.analyze_company()
        advice_task = crew_instance.advise_investment()

        self.assertTrue(news_task.async_execution)
        self.assertTrue(financial_task.async_execution)

        self.assertEqual(len(analysis_task.context), 2)
        analysis_context_descriptions = [ctx.description for ctx in analysis_task.context]
        self.assertTrue(any("Collect recent news" in text for text in analysis_context_descriptions))
        self.assertTrue(any("Gather structured financial evidence" in text for text in analysis_context_descriptions))

        self.assertEqual(len(advice_task.context), 1)
        self.assertIn("Synthesize upstream news", advice_task.context[0].description)

    @patch.dict(
        os.environ,
        {
            "OPENROUTER_MODEL": "openrouter/free-model",
            "OPENROUTER_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_final_task_writes_report_file(self):
        task = AutomationCrew().advise_investment()
        self.assertEqual(task.output_file, "report.md")
