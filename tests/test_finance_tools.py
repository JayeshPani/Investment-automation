from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_crew.tools.finance_tools import (  # noqa: E402
    GetCompanyInfoTool,
    GetCurrentStockPriceTool,
    GetFinancialStatementsTool,
)


class FakeRow:
    def __init__(self, values):
        self._values = values

    def dropna(self):
        return FakeRow([v for v in self._values if v is not None])

    def tolist(self):
        return list(self._values)


class FakeLoc:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, key):
        return FakeRow(self._rows[key])


class FakeFrame:
    def __init__(self, rows):
        self._rows = rows
        self.index = list(rows.keys())
        self.empty = not bool(rows)
        self.loc = FakeLoc(rows)


class FakeHistory(dict):
    @property
    def empty(self):
        return not bool(self)


class FinanceToolsTests(TestCase):
    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_company_info_success(self, mock_load_yfinance):
        ticker_obj = MagicMock()
        ticker_obj.info = {
            "longName": "Morgan Stanley",
            "sector": "Financial Services",
            "industry": "Capital Markets",
            "marketCap": 1000000000,
            "beta": 1.1,
            "trailingPE": 15.2,
            "forwardPE": 12.3,
            "revenueGrowth": 0.11,
            "profitMargins": 0.19,
        }
        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = ticker_obj
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetCompanyInfoTool()._run("MS"))

        self.assertEqual(output["ticker"], "MS")
        self.assertEqual(output["company_name"], "Morgan Stanley")
        self.assertEqual(output["market_cap"], 1000000000.0)
        self.assertEqual(output["data_quality_notes"], [])

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_company_info_handles_exception(self, mock_load_yfinance):
        mock_yf = MagicMock()
        mock_yf.Ticker.side_effect = RuntimeError("boom")
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetCompanyInfoTool()._run("MS"))

        self.assertIn("error", output)
        self.assertIn("data_quality_notes", output)

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_financial_statements_success(self, mock_load_yfinance):
        ticker_obj = MagicMock()
        ticker_obj.financials = FakeFrame(
            {
                "Total Revenue": [1000, 800],
                "Net Income": [200, 100],
                "Operating Income": [250, 150],
            }
        )
        ticker_obj.quarterly_financials = FakeFrame(
            {
                "Total Revenue": [300, 280],
                "Net Income": [70, 65],
            }
        )
        ticker_obj.balance_sheet = FakeFrame(
            {
                "Total Assets": [5000, 4800],
                "Total Liab": [2500, 2400],
                "Cash And Cash Equivalents": [600, 500],
            }
        )
        ticker_obj.quarterly_balance_sheet = FakeFrame(
            {
                "Total Assets": [5100, 5000],
                "Total Liab": [2550, 2500],
            }
        )
        ticker_obj.cashflow = FakeFrame(
            {
                "Operating Cash Flow": [400, 350],
                "Free Cash Flow": [300, 220],
            }
        )
        ticker_obj.quarterly_cashflow = FakeFrame(
            {
                "Operating Cash Flow": [120, 100],
            }
        )

        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = ticker_obj
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetFinancialStatementsTool()._run("MS"))

        self.assertEqual(output["annual"]["income_statement"]["total_revenue"], 1000.0)
        self.assertEqual(output["deltas"]["annual_revenue_growth_pct"], 25.0)
        self.assertEqual(output["data_quality_notes"], [])

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_financial_statements_handles_missing(self, mock_load_yfinance):
        ticker_obj = MagicMock()
        ticker_obj.financials = None
        ticker_obj.quarterly_financials = None
        ticker_obj.balance_sheet = None
        ticker_obj.quarterly_balance_sheet = None
        ticker_obj.cashflow = None
        ticker_obj.quarterly_cashflow = None

        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = ticker_obj
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetFinancialStatementsTool()._run("MS"))

        self.assertEqual(output["annual"]["income_statement"]["total_revenue"], "N/A")
        self.assertTrue(output["data_quality_notes"])

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_current_stock_price_success(self, mock_load_yfinance):
        ticker_obj = MagicMock()
        ticker_obj.info = {
            "currentPrice": 120.5,
            "fiftyTwoWeekHigh": 140.0,
            "fiftyTwoWeekLow": 90.0,
            "averageVolume": 2000000,
        }
        ticker_obj.history.return_value = FakeHistory(
            {
                "Close": [90.0, 95.0, 100.0, 110.0, 120.0, 121.0],
                "Volume": [100, 150, 120, 130, 180, 190],
            }
        )

        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = ticker_obj
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetCurrentStockPriceTool()._run("MS"))

        self.assertEqual(output["current_price"], 120.5)
        self.assertEqual(output["range_52_week"]["high"], 140.0)
        self.assertIn("1m", output["price_change_pct"])

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_get_current_stock_price_handles_exception(self, mock_load_yfinance):
        mock_yf = MagicMock()
        mock_yf.Ticker.side_effect = RuntimeError("network")
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(GetCurrentStockPriceTool()._run("MS"))

        self.assertIn("error", output)
        self.assertTrue(output["data_quality_notes"])

    @patch("automation_crew.tools.finance_tools._load_yfinance")
    def test_india_ticker_resolution_prefers_exchange_suffix(self, mock_load_yfinance):
        ticker_ns = MagicMock()
        ticker_ns.info = {
            "longName": "Reliance Industries Limited",
            "sector": "Energy",
            "industry": "Oil & Gas",
            "marketCap": 1000,
            "beta": 1.0,
            "trailingPE": 20.0,
            "forwardPE": 18.5,
            "revenueGrowth": 0.07,
            "profitMargins": 0.11,
        }
        ticker_ns.history.return_value = FakeHistory({"Close": [1.0, 1.1]})

        ticker_bo = MagicMock()
        ticker_bo.info = {}
        ticker_bo.history.return_value = FakeHistory({})

        ticker_plain = MagicMock()
        ticker_plain.info = {}
        ticker_plain.history.return_value = FakeHistory({})

        symbol_map = {
            "RELIANCE.NS": ticker_ns,
            "RELIANCE.BO": ticker_bo,
            "RELIANCE": ticker_plain,
        }

        mock_yf = MagicMock()
        mock_yf.Ticker.side_effect = lambda symbol: symbol_map[symbol]
        mock_load_yfinance.return_value = mock_yf

        output = json.loads(
            GetCompanyInfoTool()._run(
                "RELIANCE",
                market="india",
                exchange_preference="NSE",
            )
        )

        self.assertEqual(output["requested_ticker"], "RELIANCE")
        self.assertEqual(output["ticker"], "RELIANCE.NS")
        self.assertEqual(output["company_name"], "Reliance Industries Limited")
        self.assertTrue(
            any("Resolved ticker 'RELIANCE' to 'RELIANCE.NS'" in note for note in output["data_quality_notes"])
        )
