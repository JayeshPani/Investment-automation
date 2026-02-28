from __future__ import annotations

import json
import os
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _load_yfinance() -> Any:
    import yfinance as yf

    return yf


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_serializable(value: Any) -> Any:
    as_float = _to_float(value)
    if as_float is not None:
        return round(as_float, 4)

    if value is None:
        return "N/A"

    text = str(value).strip()
    return text if text else "N/A"


def _series_to_list(series: Any) -> list[Any]:
    if series is None:
        return []

    if hasattr(series, "dropna"):
        try:
            series = series.dropna()
        except Exception:
            pass

    if hasattr(series, "tolist"):
        try:
            values = series.tolist()
            return values if isinstance(values, list) else [values]
        except Exception:
            pass

    if isinstance(series, (list, tuple)):
        return list(series)

    return [series]


def _get_statement_row_values(statement: Any, line_item: str) -> list[Any]:
    if statement is None or getattr(statement, "empty", True):
        return []

    index_values = list(getattr(statement, "index", []))
    if not index_values:
        return []

    lookup = {str(item).strip().lower(): item for item in index_values}
    key = lookup.get(line_item.strip().lower())
    if key is None:
        return []

    try:
        row = statement.loc[key]
    except Exception:
        return []

    return _series_to_list(row)


def _latest_and_previous(statement: Any, line_item: str) -> tuple[Any, Any]:
    values = [_to_float(v) for v in _get_statement_row_values(statement, line_item)]
    values = [v for v in values if v is not None]

    if not values:
        return "N/A", "N/A"

    latest = round(values[0], 4)
    previous = round(values[1], 4) if len(values) > 1 else "N/A"
    return latest, previous


def _pct_change(current: Any, previous: Any) -> Any:
    current_v = _to_float(current)
    previous_v = _to_float(previous)
    if current_v is None or previous_v is None or previous_v == 0:
        return "N/A"

    return round(((current_v - previous_v) / abs(previous_v)) * 100, 2)


def _normalize_market(market: str | None) -> str:
    raw = (market or "").strip().lower()
    if not raw:
        raw = os.getenv("MARKET", "global").strip().lower()

    if raw in {"india", "indian", "in", "nse", "bse"}:
        return "india"
    return "global"


def _normalize_exchange_preference(exchange_preference: str | None) -> str:
    raw = (exchange_preference or "").strip().upper()
    if not raw:
        raw = os.getenv("EXCHANGE_PREFERENCE", "NSE").strip().upper()

    if raw in {"BSE", "BO", ".BO"}:
        return "BSE"
    return "NSE"


def _candidate_tickers(
    ticker: str, market: str, exchange_preference: str
) -> list[str]:
    base = ticker.strip().upper()
    if not base:
        return [base]

    if "." in base:
        return [base]

    if market != "india":
        return [base]

    if exchange_preference == "BSE":
        ordered = [f"{base}.BO", f"{base}.NS", base]
    else:
        ordered = [f"{base}.NS", f"{base}.BO", base]

    deduped: list[str] = []
    for symbol in ordered:
        if symbol not in deduped:
            deduped.append(symbol)
    return deduped


def _looks_valid_ticker(ticker_obj: Any) -> bool:
    try:
        info = getattr(ticker_obj, "info", None) or {}
        if any(
            info.get(key) not in (None, "", "N/A")
            for key in (
                "symbol",
                "shortName",
                "longName",
                "marketCap",
                "currentPrice",
                "regularMarketPrice",
            )
        ):
            return True
    except Exception:
        pass

    try:
        history = ticker_obj.history(period="5d", interval="1d")
        if history is not None and not getattr(history, "empty", True):
            return True
    except Exception:
        pass

    return False


def _resolve_ticker_object(
    yf: Any,
    ticker: str,
    market: str,
    exchange_preference: str,
) -> tuple[str, Any, list[str]]:
    candidates = _candidate_tickers(ticker, market, exchange_preference)
    notes: list[str] = []
    fallback_obj = None
    last_error: Exception | None = None

    for candidate in candidates:
        try:
            ticker_obj = yf.Ticker(candidate)
            fallback_obj = ticker_obj
            if _looks_valid_ticker(ticker_obj):
                requested = ticker.strip().upper()
                if candidate != requested:
                    notes.append(
                        f"Resolved ticker '{requested}' to '{candidate}' for yfinance lookup."
                    )
                return candidate, ticker_obj, notes
        except Exception as exc:
            last_error = exc

    if fallback_obj is not None:
        return candidates[-1], fallback_obj, notes

    if last_error is not None:
        raise last_error

    raise RuntimeError("Unable to initialize ticker object.")


class TickerInput(BaseModel):
    ticker: str = Field(..., description="Public ticker symbol, e.g., MS")
    market: str = Field(
        default="",
        description="Optional market context: use 'india' for NSE/BSE routing.",
    )
    exchange_preference: str = Field(
        default="",
        description="Optional preferred exchange for India: NSE or BSE.",
    )


class GetCompanyInfoTool(BaseTool):
    name: str = "get_company_info"
    description: str = (
        "Get company profile and key fundamental metrics for a ticker using yfinance."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(
        self,
        ticker: str,
        market: str = "",
        exchange_preference: str = "",
    ) -> str:
        requested_ticker = ticker.strip().upper()
        notes: list[str] = []

        try:
            yf = _load_yfinance()
            market_value = _normalize_market(market)
            exchange_value = _normalize_exchange_preference(exchange_preference)
            ticker_value, ticker_obj, resolution_notes = _resolve_ticker_object(
                yf,
                requested_ticker,
                market_value,
                exchange_value,
            )
            notes.extend(resolution_notes)
            info = ticker_obj.info or {}
        except Exception as exc:
            payload = {
                "ticker": requested_ticker,
                "error": f"Failed to fetch company info: {exc}",
                "data_quality_notes": ["Company info request failed."],
            }
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)

        payload = {
            "requested_ticker": requested_ticker,
            "ticker": ticker_value,
            "company_name": _to_serializable(info.get("longName")),
            "sector": _to_serializable(info.get("sector")),
            "industry": _to_serializable(info.get("industry")),
            "market_cap": _to_serializable(info.get("marketCap")),
            "beta": _to_serializable(info.get("beta")),
            "trailing_pe": _to_serializable(info.get("trailingPE")),
            "forward_pe": _to_serializable(info.get("forwardPE")),
            "revenue_growth": _to_serializable(info.get("revenueGrowth")),
            "profit_margins": _to_serializable(info.get("profitMargins")),
            "data_quality_notes": notes,
        }

        for key in (
            "company_name",
            "sector",
            "industry",
            "market_cap",
            "trailing_pe",
            "forward_pe",
            "revenue_growth",
            "profit_margins",
        ):
            if payload[key] == "N/A":
                notes.append(f"Missing value for '{key}'.")

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class GetFinancialStatementsTool(BaseTool):
    name: str = "get_financial_statements"
    description: str = (
        "Get annual and quarterly income statement, balance sheet, and cash flow "
        "highlights with simple growth deltas."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(
        self,
        ticker: str,
        market: str = "",
        exchange_preference: str = "",
    ) -> str:
        requested_ticker = ticker.strip().upper()
        notes: list[str] = []

        try:
            yf = _load_yfinance()
            market_value = _normalize_market(market)
            exchange_value = _normalize_exchange_preference(exchange_preference)
            ticker_value, ticker_obj, resolution_notes = _resolve_ticker_object(
                yf,
                requested_ticker,
                market_value,
                exchange_value,
            )
            notes.extend(resolution_notes)
        except Exception as exc:
            payload = {
                "ticker": requested_ticker,
                "error": f"Failed to initialize yfinance ticker: {exc}",
                "data_quality_notes": ["Financial statement fetch failed."],
            }
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)

        annual_income = getattr(ticker_obj, "financials", None)
        quarterly_income = getattr(ticker_obj, "quarterly_financials", None)
        annual_balance = getattr(ticker_obj, "balance_sheet", None)
        quarterly_balance = getattr(ticker_obj, "quarterly_balance_sheet", None)
        annual_cash = getattr(ticker_obj, "cashflow", None)
        quarterly_cash = getattr(ticker_obj, "quarterly_cashflow", None)

        annual_revenue_latest, annual_revenue_previous = _latest_and_previous(
            annual_income, "Total Revenue"
        )
        annual_net_income_latest, annual_net_income_previous = _latest_and_previous(
            annual_income, "Net Income"
        )

        payload = {
            "requested_ticker": requested_ticker,
            "ticker": ticker_value,
            "annual": {
                "income_statement": {
                    "total_revenue": annual_revenue_latest,
                    "net_income": annual_net_income_latest,
                    "operating_income": _latest_and_previous(
                        annual_income, "Operating Income"
                    )[0],
                },
                "balance_sheet": {
                    "total_assets": _latest_and_previous(annual_balance, "Total Assets")[
                        0
                    ],
                    "total_liabilities": _latest_and_previous(
                        annual_balance, "Total Liab"
                    )[0],
                    "cash_and_equivalents": _latest_and_previous(
                        annual_balance, "Cash And Cash Equivalents"
                    )[0],
                },
                "cash_flow": {
                    "operating_cash_flow": _latest_and_previous(
                        annual_cash, "Operating Cash Flow"
                    )[0],
                    "free_cash_flow": _latest_and_previous(
                        annual_cash, "Free Cash Flow"
                    )[0],
                },
            },
            "quarterly": {
                "income_statement": {
                    "total_revenue": _latest_and_previous(
                        quarterly_income, "Total Revenue"
                    )[0],
                    "net_income": _latest_and_previous(
                        quarterly_income, "Net Income"
                    )[0],
                },
                "balance_sheet": {
                    "total_assets": _latest_and_previous(
                        quarterly_balance, "Total Assets"
                    )[0],
                    "total_liabilities": _latest_and_previous(
                        quarterly_balance, "Total Liab"
                    )[0],
                },
                "cash_flow": {
                    "operating_cash_flow": _latest_and_previous(
                        quarterly_cash, "Operating Cash Flow"
                    )[0],
                },
            },
            "deltas": {
                "annual_revenue_growth_pct": _pct_change(
                    annual_revenue_latest, annual_revenue_previous
                ),
                "annual_net_income_growth_pct": _pct_change(
                    annual_net_income_latest, annual_net_income_previous
                ),
            },
            "data_quality_notes": notes,
        }

        critical_paths = [
            payload["annual"]["income_statement"]["total_revenue"],
            payload["annual"]["income_statement"]["net_income"],
            payload["annual"]["balance_sheet"]["total_assets"],
            payload["annual"]["cash_flow"]["operating_cash_flow"],
        ]
        if all(value == "N/A" for value in critical_paths):
            notes.append(
                "Annual statement fields were not available from yfinance for this ticker."
            )

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class GetCurrentStockPriceTool(BaseTool):
    name: str = "get_current_stock_price"
    description: str = (
        "Get current stock price snapshot, 52-week range, volume, and 1m/3m/1y "
        "price change percentages."
    )
    args_schema: Type[BaseModel] = TickerInput

    def _run(
        self,
        ticker: str,
        market: str = "",
        exchange_preference: str = "",
    ) -> str:
        requested_ticker = ticker.strip().upper()
        notes: list[str] = []

        try:
            yf = _load_yfinance()
            market_value = _normalize_market(market)
            exchange_value = _normalize_exchange_preference(exchange_preference)
            ticker_value, ticker_obj, resolution_notes = _resolve_ticker_object(
                yf,
                requested_ticker,
                market_value,
                exchange_value,
            )
            notes.extend(resolution_notes)
            info = ticker_obj.info or {}
            history = ticker_obj.history(period="1y", interval="1d")
        except Exception as exc:
            payload = {
                "ticker": requested_ticker,
                "error": f"Failed to fetch stock price data: {exc}",
                "data_quality_notes": ["Stock price request failed."],
            }
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)

        closes: list[float] = []
        volumes: list[float] = []

        if history is not None and not getattr(history, "empty", True):
            close_series = None
            volume_series = None
            try:
                close_series = history["Close"]
                volume_series = history["Volume"]
            except Exception:
                if hasattr(history, "get"):
                    close_series = history.get("Close")
                    volume_series = history.get("Volume")

            closes = [
                value
                for value in (_to_float(v) for v in _series_to_list(close_series))
                if value is not None
            ]
            volumes = [
                value
                for value in (_to_float(v) for v in _series_to_list(volume_series))
                if value is not None
            ]

        current_price = _to_float(info.get("currentPrice"))
        if current_price is None and closes:
            current_price = closes[-1]

        high_52_week = _to_float(info.get("fiftyTwoWeekHigh"))
        low_52_week = _to_float(info.get("fiftyTwoWeekLow"))

        if high_52_week is None and closes:
            high_52_week = max(closes)
        if low_52_week is None and closes:
            low_52_week = min(closes)

        average_volume = _to_float(info.get("averageVolume"))
        if average_volume is None and volumes:
            sample = volumes[-30:] if len(volumes) > 30 else volumes
            average_volume = sum(sample) / len(sample)

        def change_pct(bars_back: int) -> Any:
            if len(closes) <= bars_back:
                return "N/A"
            current = closes[-1]
            previous = closes[-(bars_back + 1)]
            return _pct_change(current, previous)

        payload = {
            "requested_ticker": requested_ticker,
            "ticker": ticker_value,
            "current_price": _to_serializable(current_price),
            "range_52_week": {
                "low": _to_serializable(low_52_week),
                "high": _to_serializable(high_52_week),
            },
            "average_volume": _to_serializable(average_volume),
            "price_change_pct": {
                "1m": change_pct(21),
                "3m": change_pct(63),
                "1y": change_pct(252),
            },
            "data_quality_notes": notes,
        }

        if payload["current_price"] == "N/A":
            notes.append("Current price was unavailable from yfinance.")
        if payload["price_change_pct"]["1y"] == "N/A":
            notes.append("Insufficient price history for full 1-year change.")

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
