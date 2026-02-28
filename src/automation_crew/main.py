#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime
from typing import Any

from automation_crew.crew import AutomationCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

REQUIRED_ENV_VARS = ("OPENROUTER_API_KEY", "OPENROUTER_MODEL")


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        return ""
    return value.strip()


def _positive_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        parsed = int(raw)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


def normalize_market(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"india", "indian", "in", "nse", "bse"}:
        return "india"
    return "global"


def normalize_exchange_preference(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if raw in {"BSE", "BO", ".BO"}:
        return "BSE"
    return "NSE"


def normalize_input_ticker(
    ticker: str | None,
    market: str,
    exchange_preference: str,
) -> str:
    normalized = (ticker or "").strip().upper()
    if not normalized or "." in normalized:
        return normalized

    if normalize_market(market) == "india":
        exchange = normalize_exchange_preference(exchange_preference)
        suffix = ".BO" if exchange == "BSE" else ".NS"
        return f"{normalized}{suffix}"

    return normalized


def build_inputs_from_env() -> dict[str, Any]:
    market = normalize_market(_env("MARKET", "global"))
    exchange_preference = normalize_exchange_preference(
        _env("EXCHANGE_PREFERENCE", "NSE")
    )
    ticker = normalize_input_ticker(
        _env("COMPANY_TICKER"),
        market,
        exchange_preference,
    )

    return {
        "ticker": ticker,
        "company_name": _env("COMPANY_NAME"),
        "market": market,
        "exchange_preference": exchange_preference,
        "investor_profile": _env("INVESTOR_PROFILE", "moderate"),
        "analysis_horizon_days": _positive_int("ANALYSIS_HORIZON_DAYS", 365),
        "news_lookback_days": _positive_int("NEWS_LOOKBACK_DAYS", 30),
        "current_year": str(datetime.now().year),
    }


def validate_runtime_environment(inputs: dict[str, Any] | None = None) -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not _env(name)]

    resolved_inputs = inputs or build_inputs_from_env()
    ticker = str(resolved_inputs.get("ticker", "")).strip()
    company_name = str(resolved_inputs.get("company_name", "")).strip()

    if not ticker:
        missing.append("COMPANY_TICKER (or inputs['ticker'])")
    if not company_name:
        missing.append("COMPANY_NAME (or inputs['company_name'])")

    if missing:
        missing_values = ", ".join(missing)
        raise ValueError(
            f"Missing required configuration: {missing_values}. "
            "Check your .env file before running the crew."
        )


def run() -> Any:
    """Run the crew."""
    inputs = build_inputs_from_env()
    validate_runtime_environment(inputs)

    try:
        return AutomationCrew().crew().kickoff(inputs=inputs)
    except Exception as exc:
        raise Exception(f"An error occurred while running the crew: {exc}") from exc


def train() -> Any:
    """Train the crew for a given number of iterations."""
    inputs = build_inputs_from_env()
    validate_runtime_environment(inputs)

    try:
        return AutomationCrew().crew().train(
            n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs
        )
    except Exception as exc:
        raise Exception(f"An error occurred while training the crew: {exc}") from exc


def replay() -> Any:
    """Replay the crew execution from a specific task."""
    try:
        return AutomationCrew().crew().replay(task_id=sys.argv[1])
    except Exception as exc:
        raise Exception(f"An error occurred while replaying the crew: {exc}") from exc


def test() -> Any:
    """Test crew execution and return results."""
    inputs = build_inputs_from_env()
    validate_runtime_environment(inputs)

    try:
        return AutomationCrew().crew().test(
            n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs
        )
    except Exception as exc:
        raise Exception(f"An error occurred while testing the crew: {exc}") from exc


def run_with_trigger() -> Any:
    """Run the crew with trigger payload."""
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        raise Exception("Invalid JSON payload provided as argument") from exc

    inputs = build_inputs_from_env()
    for key in (
        "ticker",
        "company_name",
        "market",
        "exchange_preference",
        "investor_profile",
        "analysis_horizon_days",
        "news_lookback_days",
    ):
        if key in trigger_payload and trigger_payload[key] is not None:
            inputs[key] = trigger_payload[key]

    inputs["market"] = normalize_market(str(inputs.get("market", "")))
    inputs["exchange_preference"] = normalize_exchange_preference(
        str(inputs.get("exchange_preference", ""))
    )
    inputs["ticker"] = normalize_input_ticker(
        str(inputs.get("ticker", "")),
        str(inputs.get("market", "global")),
        str(inputs.get("exchange_preference", "NSE")),
    )

    inputs["crewai_trigger_payload"] = trigger_payload
    validate_runtime_environment(inputs)

    try:
        return AutomationCrew().crew().kickoff(inputs=inputs)
    except Exception as exc:
        raise Exception(
            f"An error occurred while running the crew with trigger: {exc}"
        ) from exc
