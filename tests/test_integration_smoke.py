from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_crew.crew import AutomationCrew  # noqa: E402


class IntegrationSmokeTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "OPENROUTER_MODEL": "openrouter/free-model",
            "OPENROUTER_API_KEY": "test-key",
        },
        clear=False,
    )
    @patch("automation_crew.tools.news_tools.CompanyNewsSearchTool._run")
    @patch("automation_crew.tools.finance_tools.GetCompanyInfoTool._run")
    @patch("automation_crew.tools.finance_tools.GetFinancialStatementsTool._run")
    @patch("automation_crew.tools.finance_tools.GetCurrentStockPriceTool._run")
    @patch("crewai.agent.core.Agent.execute_task")
    def test_smoke_pipeline_generates_report(
        self,
        mock_execute_task,
        mock_stock_price,
        mock_financials,
        mock_company_info,
        mock_news,
    ):
        mock_news.return_value = '{"ticker":"MS","articles":[{"title":"Sample","url":"https://example.com"}],"source_confidence":"high"}'
        mock_company_info.return_value = '{"ticker":"MS","company_name":"Morgan Stanley"}'
        mock_financials.return_value = '{"ticker":"MS","annual":{"income_statement":{"total_revenue":1000}}}'
        mock_stock_price.return_value = '{"ticker":"MS","current_price":100.0}'

        def fake_execute(*call_args, **call_kwargs):
            if not call_args:
                task = call_kwargs.get("task")
                tools = call_kwargs.get("tools")
            elif hasattr(call_args[0], "description"):
                task = call_args[0]
                tools = call_args[2] if len(call_args) > 2 else call_kwargs.get("tools")
            else:
                task = call_args[1]
                tools = call_args[3] if len(call_args) > 3 else call_kwargs.get("tools")

            description = task.description.lower()

            if "collect recent news" in description:
                return tools[0]._run(ticker="MS", company_name="Morgan Stanley", lookback_days=30)

            if "gather structured financial evidence" in description:
                info = tools[0]._run(ticker="MS")
                statements = tools[1]._run(ticker="MS")
                return f"{{\"company_info\":{info},\"statements\":{statements}}}"

            if "synthesize upstream news" in description:
                return (
                    "## Executive Summary\n"
                    "Synthetic analysis generated from mocked news and financial data.\n"
                    "## Data Gaps\n"
                    "No critical gaps in smoke test."
                )

            latest_price = tools[0]._run(ticker="MS") if tools else "{}"
            return (
                "Decision (Invest/Do Not Invest/Hold): Hold\n"
                "Confidence (0-100): 63\n"
                "Time Horizon View (30/90/365 days): Neutral/Neutral/Positive\n"
                "Bull Case: Durable earnings and capital return.\n"
                "Bear Case: Macro slowdown and revenue pressure.\n"
                "Key Risks: Credit cycle, regulation.\n"
                "Risk Controls: Position sizing and stop-loss discipline.\n"
                "Data Gaps: None in smoke test.\n"
                "Disclaimer: This is informational analysis, not financial advice.\n"
                f"Latest price snapshot: {latest_price}"
            )

        mock_execute_task.side_effect = fake_execute

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            cwd = os.getcwd()
            original_home = os.environ.get("HOME")
            os.chdir(temp_dir)
            os.environ["HOME"] = temp_dir
            try:
                with patch("appdirs.user_data_dir", return_value=temp_dir):
                    crew = AutomationCrew().crew()
                    crew.kickoff(
                        inputs={
                            "ticker": "MS",
                            "company_name": "Morgan Stanley",
                            "market": "global",
                            "exchange_preference": "NSE",
                            "investor_profile": "moderate",
                            "analysis_horizon_days": 365,
                            "news_lookback_days": 30,
                            "current_year": "2026",
                        }
                    )

                report_path = Path(temp_dir) / "report.md"
                self.assertTrue(report_path.exists())
                report_text = report_path.read_text(encoding="utf-8")
                self.assertIn("Decision (Invest/Do Not Invest/Hold)", report_text)
                self.assertIn("Disclaimer: This is informational analysis, not financial advice.", report_text)
            finally:
                os.chdir(cwd)
                if original_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = original_home
