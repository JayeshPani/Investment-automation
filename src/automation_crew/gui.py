from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import gradio as gr

from automation_crew.crew import AutomationCrew
from automation_crew.main import (
    build_inputs_from_env,
    normalize_exchange_preference,
    normalize_input_ticker,
    normalize_market,
    validate_runtime_environment,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "report.md"
ENV_PATH = PROJECT_ROOT / ".env"

RECOMMENDATION_FIELDS = [
    "Decision (Invest/Do Not Invest/Hold)",
    "Confidence (0-100)",
    "Time Horizon View (30/90/365 days)",
    "Bull Case",
    "Bear Case",
    "Key Risks",
    "Risk Controls",
    "Data Gaps",
    "Disclaimer",
]

INDIA_TICKER_HINTS = {
    "RELIANCE",
    "HDFC",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "TCS",
    "INFY",
    "WIPRO",
    "LT",
    "LTIM",
    "AXISBANK",
    "KOTAKBANK",
    "BAJFINANCE",
    "HINDUNILVR",
    "ITC",
    "MARUTI",
    "SUNPHARMA",
    "TITAN",
    "ADANIENT",
    "ADANIPORTS",
    "POWERGRID",
    "ULTRACEMCO",
    "ONGC",
    "NTPC",
}

INDIA_COMPANY_HINT_KEYWORDS = (
    "reliance",
    "hdfc",
    "icici",
    "infosys",
    "adani",
    "mahindra",
    "kotak",
    "bajaj",
    "maruti",
    "sun pharma",
    "hindustan unilever",
    "nifty",
    "sensex",
)


class _NoopTaskOutputStorageHandler:
    """Fallback handler when CrewAI local SQLite storage is not writable."""

    def reset(self) -> None:
        return

    def add(self, *args: Any, **kwargs: Any) -> None:
        return

    def update(self, *args: Any, **kwargs: Any) -> None:
        return

    def load(self) -> list[dict[str, Any]]:
        return []


CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
  --bg: #0a0f1d;
  --panel: #111827;
  --panel-soft: #0f172a;
  --report-bg: #0b1220;
  --ink: #e5e7eb;
  --forest: #0f5132;
  --forest-soft: #166534;
  --gold: #f59e0b;
  --line: rgba(148, 163, 184, 0.28);
  --muted: #94a3b8;
}

.gradio-container {
  background: radial-gradient(circle at 15% 10%, #172554 0%, #0b1220 40%, #030712 100%);
  color: var(--ink);
  font-family: Inter, system-ui, sans-serif;
}

.app-shell {
  max-width: 1360px !important;
  margin: 0 auto;
  padding: 20px 20px 30px 20px;
}

.hero {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: linear-gradient(120deg, rgba(22, 101, 52, 0.35), rgba(15, 23, 42, 0.9));
  margin-bottom: 16px;
  padding: 18px;
}

.hero h1 {
  margin: 0;
  color: var(--forest);
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size: 30px;
  line-height: 1.1;
}

.hero p {
  margin: 8px 0 0 0;
  color: #cbd5e1;
  font-size: 14px;
}

.dashboard {
  gap: 14px;
}

.control-panel,
.output-panel {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--panel);
}

.control-panel {
  padding: 14px;
}

.output-panel {
  padding: 14px;
}

.panel-title {
  margin: 0 0 10px 0;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 11px;
  color: var(--muted);
}

#run-btn {
  background: linear-gradient(135deg, #166534, #15803d) !important;
  border: 1px solid var(--forest-soft) !important;
  color: #f8fafc !important;
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-weight: 600;
}

#run-btn:hover {
  filter: brightness(1.04);
}

#reload-btn {
  border: 1px solid var(--line) !important;
  color: var(--ink) !important;
  background: var(--panel-soft) !important;
}

.control-panel input,
.control-panel textarea,
.control-panel select,
.control-panel .gradio-dropdown,
.control-panel .gradio-textbox,
.control-panel .gradio-slider {
  background: var(--panel-soft) !important;
  color: var(--ink) !important;
  border-color: var(--line) !important;
}

.control-panel label,
.output-panel label {
  color: #dbeafe !important;
}

#report-box {
  min-height: 500px;
  max-height: 640px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px;
  background: var(--report-bg);
  color: #f8fafc !important;
}

#report-box * {
  color: #e5e7eb !important;
}

#report-box h1,
#report-box h2,
#report-box h3,
#report-box h4 {
  color: #f8fafc !important;
}

#report-box a {
  color: #7dd3fc !important;
  text-decoration: underline;
}

#report-box code,
#report-box pre {
  background: #111827 !important;
  color: #f3f4f6 !important;
}

#status-box {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 10px;
  background: #111827;
  color: #e2e8f0 !important;
}

#recommendation-box {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #0b1220 !important;
  color: #e5e7eb !important;
}

#raw-output textarea {
  background: #0b1220 !important;
  color: #e5e7eb !important;
  border-color: var(--line) !important;
  font-family: 'JetBrains Mono', ui-monospace, monospace !important;
  font-size: 12px !important;
}

@media (max-width: 900px) {
  .app-shell {
    padding: 12px;
  }

  .hero h1 {
    font-size: 24px;
  }

  #report-box {
    min-height: 360px;
  }
}
"""


def _load_dotenv_file() -> None:
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        os.environ.setdefault(key, value)


def _parse_markdown_sections(markdown_text: str) -> dict[str, str]:
    sections: dict[str, str] = {field: "Not found in report." for field in RECOMMENDATION_FIELDS}

    if not markdown_text.strip():
        return sections

    normalized_targets = {field.lower(): field for field in RECOMMENDATION_FIELDS}
    alias_to_target = {
        "decision": "Decision (Invest/Do Not Invest/Hold)",
        "confidence": "Confidence (0-100)",
        "time horizon view": "Time Horizon View (30/90/365 days)",
        "time horizon": "Time Horizon View (30/90/365 days)",
        "horizon view": "Time Horizon View (30/90/365 days)",
    }
    for alias, target in alias_to_target.items():
        normalized_targets.setdefault(alias, target)

    def _clean_title_text(line: str) -> str:
        text = line.strip()
        text = re.sub(r"^#+\s*", "", text)
        text = re.sub(r"^\d+\.\s*", "", text)
        return text.strip().strip("*").strip()

    def line_to_title(line: str) -> tuple[str | None, str]:
        text = _clean_title_text(line)
        if not text:
            return None, ""

        inline_value = ""
        title_candidate = text
        if ":" in text:
            left, right = text.split(":", 1)
            title_candidate = left.strip()
            inline_value = right.strip()

        normalized = title_candidate.rstrip(":").strip().lower()
        return normalized_targets.get(normalized), inline_value

    lines = markdown_text.splitlines()
    current_title: str | None = None
    buffer: list[str] = []

    for line in lines:
        maybe_title, inline_value = line_to_title(line)
        if maybe_title is not None:
            if current_title is not None:
                content = "\n".join(buffer).strip()
                sections[current_title] = content or "Present but empty."
            current_title = maybe_title
            buffer = [inline_value] if inline_value else []
            continue

        if current_title is not None:
            buffer.append(line)

    if current_title is not None:
        content = "\n".join(buffer).strip()
        sections[current_title] = content or "Present but empty."

    return sections


def _coerce_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _error_sections(error_message: str) -> dict[str, str]:
    compact_error = _compact_error_message(error_message)
    sections = {
        field: "Not available due to runtime error." for field in RECOMMENDATION_FIELDS
    }
    sections["Data Gaps"] = f"Run failed before recommendation generation. Error: {compact_error}"
    sections["Disclaimer"] = "This is informational analysis, not financial advice."
    return sections


def _in_progress_sections(stage_message: str) -> dict[str, str]:
    return {field: stage_message for field in RECOMMENDATION_FIELDS}


def _is_rate_limit_error(error_message: str) -> bool:
    lowered = error_message.lower()
    return (
        "ratelimiterror" in lowered
        or "rate limit" in lowered
        or "temporarily rate-limited" in lowered
        or '"code":429' in lowered
        or " code:429" in lowered
    )


def _is_free_model_policy_error(error_message: str) -> bool:
    lowered = error_message.lower()
    return (
        "no endpoints found matching your data policy" in lowered
        or "free model publication" in lowered
        or "configure: https://openrouter.ai/settings/privacy" in lowered
    )


def _is_model_switchable_error(error_message: str) -> bool:
    return _is_rate_limit_error(error_message) or _is_free_model_policy_error(error_message)


def _compact_error_message(error_message: str, max_length: int = 360) -> str:
    single_line = re.sub(r"\s+", " ", str(error_message)).strip()
    if len(single_line) <= max_length:
        return single_line
    return f"{single_line[: max_length - 3]}..."


def _candidate_openrouter_models() -> list[str]:
    primary = os.getenv("OPENROUTER_MODEL", "").strip()
    fallback_csv = os.getenv("OPENROUTER_MODEL_FALLBACKS", "").strip()

    candidates: list[str] = []
    if primary:
        candidates.append(primary)
    if fallback_csv:
        candidates.extend(
            model.strip() for model in fallback_csv.split(",") if model.strip()
        )

    # Preserve order while deduplicating.
    ordered_unique: list[str] = []
    for model in candidates:
        if model not in ordered_unique:
            ordered_unique.append(model)

    return ordered_unique


def _result_to_text(result: Any) -> str:
    if result is None:
        return ""

    for attr in ("raw", "output", "result"):
        if hasattr(result, attr):
            value = getattr(result, attr)
            if value is not None:
                return str(value)

    return str(result)


def _resolved_defaults() -> dict[str, Any]:
    _load_dotenv_file()
    defaults = build_inputs_from_env()
    return {
        "ticker": defaults.get("ticker", ""),
        "company_name": defaults.get("company_name", ""),
        "market": normalize_market(str(defaults.get("market", "global"))),
        "exchange_preference": normalize_exchange_preference(
            str(defaults.get("exchange_preference", "NSE"))
        ),
        "investor_profile": defaults.get("investor_profile", "moderate") or "moderate",
        "analysis_horizon_days": _coerce_int(defaults.get("analysis_horizon_days"), 365),
        "news_lookback_days": _coerce_int(defaults.get("news_lookback_days"), 30),
    }


def _is_likely_indian_input(ticker: str, company_name: str) -> bool:
    ticker_clean = (ticker or "").strip().upper()
    company_clean = (company_name or "").strip().lower()
    ticker_root = ticker_clean.split(".", 1)[0]

    if ticker_clean.endswith(".NS") or ticker_clean.endswith(".BO"):
        return True

    if ticker_root in INDIA_TICKER_HINTS:
        return True

    return any(keyword in company_clean for keyword in INDIA_COMPANY_HINT_KEYWORDS)


def suggest_market_from_inputs(
    ticker: str,
    company_name: str,
    current_market: str,
) -> tuple[str, str]:
    market_normalized = normalize_market(current_market)
    if _is_likely_indian_input(ticker, company_name) and market_normalized != "india":
        return (
            "india",
            "Auto-suggestion: switched `Market` to `india` based on ticker/company pattern.",
        )

    if market_normalized == "india":
        return (
            "india",
            "Market routing: `india`.",
        )

    return (
        "global",
        "Market routing: `global`.",
    )


def load_form_defaults() -> tuple[str, str, str, str, str, int, int, str]:
    defaults = _resolved_defaults()
    return (
        str(defaults["ticker"]),
        str(defaults["company_name"]),
        str(defaults["market"]),
        str(defaults["exchange_preference"]),
        str(defaults["investor_profile"]),
        int(defaults["analysis_horizon_days"]),
        int(defaults["news_lookback_days"]),
        "Reloaded values from `.env`.",
    )


def run_workflow(
    ticker: str,
    company_name: str,
    market: str,
    exchange_preference: str,
    investor_profile: str,
    analysis_horizon_days: int,
    news_lookback_days: int,
) -> Any:
    started = time.time()
    _load_dotenv_file()

    if not ticker.strip():
        message = "Please enter a valid stock ticker (for example `RELIANCE` or `RELIANCE.NS`)."
        yield (
            "Analysis failed.\n\n- Error: `ValidationError`\n- Message: `Ticker is required.`",
            _error_sections(message),
            f"## Run Failed\n\n{message}",
            message,
            None,
        )
        return

    if not company_name.strip():
        message = "Please enter a company name that matches the ticker."
        yield (
            "Analysis failed.\n\n- Error: `ValidationError`\n- Message: `Company Name is required.`",
            _error_sections(message),
            f"## Run Failed\n\n{message}",
            message,
            None,
        )
        return

    yield (
        "Analysis started.\n\n"
        "- Validating inputs and preparing tools...\n"
        "- Running 4-agent pipeline (news + financials in parallel)...\n"
        "- Check terminal logs for per-task execution details.",
        _in_progress_sections("Processing..."),
        "## Running Analysis\n\nPlease wait while agents gather data and synthesize the report.",
        "Pipeline is running. Raw output will appear when execution completes.",
        None,
    )

    inputs = build_inputs_from_env()
    market_value = normalize_market(market)
    exchange_value = normalize_exchange_preference(exchange_preference)

    inputs["market"] = market_value
    inputs["exchange_preference"] = exchange_value
    inputs["ticker"] = normalize_input_ticker(
        ticker,
        market_value,
        exchange_value,
    )
    inputs["company_name"] = company_name.strip()
    inputs["investor_profile"] = investor_profile.strip() or "moderate"
    inputs["analysis_horizon_days"] = _coerce_int(analysis_horizon_days, 365)
    inputs["news_lookback_days"] = _coerce_int(news_lookback_days, 30)

    try:
        validate_runtime_environment(inputs)
        max_attempts = max(1, _coerce_int(os.getenv("GUI_RATE_LIMIT_RETRIES", "3"), 3))
        retry_delays = [3, 8, 15, 25]
        candidate_models = _candidate_openrouter_models()
        original_model = os.getenv("OPENROUTER_MODEL", "")
        attempt = 1
        result = None
        model_used = original_model

        try:
            while attempt <= max_attempts and result is None:
                should_retry_attempt = False

                for model_index, candidate_model in enumerate(candidate_models or [original_model]):
                    os.environ["OPENROUTER_MODEL"] = candidate_model
                    model_used = candidate_model

                    crew_instance = AutomationCrew().crew()
                    try:
                        result = crew_instance.kickoff(inputs=inputs)
                        break
                    except Exception as kickoff_exc:  # noqa: BLE001
                        kickoff_message = str(kickoff_exc)
                        kickoff_message_lower = kickoff_message.lower()

                        if "readonly database" in kickoff_message_lower:
                            crew_instance = AutomationCrew().crew()
                            crew_instance._task_output_handler = _NoopTaskOutputStorageHandler()
                            result = crew_instance.kickoff(inputs=inputs)
                            break

                        if _is_model_switchable_error(kickoff_message):
                            has_fallback_model = model_index < len(candidate_models or [original_model]) - 1
                            if has_fallback_model:
                                next_model = (candidate_models or [original_model])[model_index + 1]
                                if _is_free_model_policy_error(kickoff_message):
                                    stage_title = "## Free Model Policy Blocked\n\nProvider rejected free model for current OpenRouter privacy policy.\nTrying fallback model."
                                    stage_text = "Policy blocked free model. Trying fallback model..."
                                else:
                                    stage_title = "## Switching Model\n\nReceived `429` from provider.\nTrying fallback model from `OPENROUTER_MODEL_FALLBACKS`."
                                    stage_text = "Rate-limited upstream. Trying fallback model..."
                                yield (
                                    "Provider is unavailable for this model. Switching model automatically...\n\n"
                                    f"- Attempt: `{attempt}/{max_attempts}`\n"
                                    f"- Current model: `{candidate_model}`\n"
                                    f"- Next model: `{next_model}`",
                                    _in_progress_sections(stage_text),
                                    stage_title,
                                    _compact_error_message(kickoff_message),
                                    None,
                                )
                                continue

                            if _is_rate_limit_error(kickoff_message) and attempt < max_attempts:
                                wait_seconds = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                                yield (
                                    "Provider is rate-limited. Retrying automatically...\n\n"
                                    f"- Attempt: `{attempt + 1}/{max_attempts}`\n"
                                    f"- Wait: `{wait_seconds}s`\n"
                                    f"- Model: `{candidate_model}`\n"
                                    "- Tip: add additional models to `OPENROUTER_MODEL_FALLBACKS`.",
                                    _in_progress_sections("Rate-limited upstream. Retrying..."),
                                    "## Waiting For Retry\n\nOpenRouter/provider returned `429`.\n"
                                    "Retrying automatically with backoff.",
                                    _compact_error_message(kickoff_message),
                                    None,
                                )
                                time.sleep(wait_seconds)
                                attempt += 1
                                should_retry_attempt = True
                                break

                        raise

                if result is not None:
                    break

                if not should_retry_attempt:
                    break
        finally:
            if original_model:
                os.environ["OPENROUTER_MODEL"] = original_model

        if result is None:
            raise RuntimeError("Crew execution did not produce a result.")

        raw_output = _result_to_text(result)

        report_text = ""
        if REPORT_PATH.exists():
            report_text = REPORT_PATH.read_text(encoding="utf-8")
        elif raw_output:
            report_text = raw_output

        sections = _parse_markdown_sections(report_text)
        elapsed = time.time() - started

        status = (
            "Analysis completed successfully.\\n\\n"
            f"- Company: `{inputs['company_name']}` ({inputs['ticker']})\\n"
            f"- Market: `{inputs['market']}` ({inputs['exchange_preference']})\\n"
            f"- Profile: `{inputs['investor_profile']}`\\n"
            f"- Horizon: `{inputs['analysis_horizon_days']}` days\\n"
            f"- Model: `{model_used}`\\n"
            f"- Runtime: `{elapsed:.1f}s`"
        )

        report_file = str(REPORT_PATH) if REPORT_PATH.exists() else None
        yield status, sections, report_text, raw_output, report_file
        return

    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        compact_error = _compact_error_message(error_message)
        error_status = (
            "Analysis failed.\\n\\n"
            f"- Error: `{type(exc).__name__}`\\n"
            f"- Message: `{compact_error}`"
        )
        report_text = (
            "## Run Failed\n\n"
            f"**Error Type:** `{type(exc).__name__}`\n\n"
            f"**Error Message:** `{compact_error}`\n\n"
            "Check inputs and provider configuration, then retry."
        )
        yield (
            error_status,
            _error_sections(error_message),
            report_text,
            compact_error,
            None,
        )
        return


def create_app() -> gr.Blocks:
    defaults = _resolved_defaults()

    with gr.Blocks(title="Investment Advisor Crew") as app:
        with gr.Column(elem_classes=["app-shell"]):
            gr.HTML(
                """
                <div class="hero">
                  <h1>Investment Advisor Crew Console</h1>
                  <p>
                    Parallel news and financial intelligence pipeline with analyst synthesis and final
                    investment recommendation.
                  </p>
                </div>
                """
            )

            with gr.Row(elem_classes=["dashboard"]):
                with gr.Column(scale=4, elem_classes=["control-panel"]):
                    gr.Markdown("### Inputs", elem_classes=["panel-title"])

                    ticker_input = gr.Textbox(
                        label="Ticker",
                        value=str(defaults["ticker"]),
                        placeholder="MS, AAPL, NVDA",
                    )
                    company_input = gr.Textbox(
                        label="Company Name",
                        value=str(defaults["company_name"]),
                        placeholder="Morgan Stanley",
                    )
                    market_input = gr.Dropdown(
                        label="Market",
                        choices=["global", "india"],
                        value=str(defaults["market"]),
                    )
                    market_hint_box = gr.Markdown(
                        "Market routing follows your selected value.",
                        elem_id="status-box",
                    )
                    exchange_input = gr.Dropdown(
                        label="Exchange Preference (India)",
                        choices=["NSE", "BSE"],
                        value=str(defaults["exchange_preference"]),
                    )
                    profile_input = gr.Dropdown(
                        label="Investor Profile",
                        choices=["conservative", "moderate", "aggressive"],
                        value=str(defaults["investor_profile"]),
                    )
                    horizon_input = gr.Slider(
                        label="Analysis Horizon (Days)",
                        minimum=30,
                        maximum=1825,
                        step=1,
                        value=int(defaults["analysis_horizon_days"]),
                    )
                    lookback_input = gr.Slider(
                        label="News Lookback (Days)",
                        minimum=1,
                        maximum=120,
                        step=1,
                        value=int(defaults["news_lookback_days"]),
                    )

                    run_btn = gr.Button("Run Full Analysis", variant="primary", elem_id="run-btn")
                    reload_btn = gr.Button("Reload From .env", elem_id="reload-btn")
                    status_box = gr.Markdown("Ready.", elem_id="status-box")

                with gr.Column(scale=8, elem_classes=["output-panel"]):
                    gr.Markdown("### Recommendation Snapshot", elem_classes=["panel-title"])
                    recommendation_box = gr.JSON(label="Extracted Recommendation Fields", elem_id="recommendation-box")

                    gr.Markdown("### Report", elem_classes=["panel-title"])
                    report_box = gr.Markdown(value="Report output will appear here.", elem_id="report-box")

                    with gr.Accordion("Raw Crew Output", open=False):
                        raw_output_box = gr.Textbox(
                            label="Raw Output",
                            lines=12,
                            interactive=False,
                            elem_id="raw-output",
                        )

                    report_file = gr.File(label="Download report.md")

            run_btn.click(
                fn=run_workflow,
                inputs=[
                    ticker_input,
                    company_input,
                    market_input,
                    exchange_input,
                    profile_input,
                    horizon_input,
                    lookback_input,
                ],
                outputs=[status_box, recommendation_box, report_box, raw_output_box, report_file],
            )

            reload_btn.click(
                fn=load_form_defaults,
                inputs=[],
                outputs=[
                    ticker_input,
                    company_input,
                    market_input,
                    exchange_input,
                    profile_input,
                    horizon_input,
                    lookback_input,
                    status_box,
                ],
            )

            ticker_input.change(
                fn=suggest_market_from_inputs,
                inputs=[ticker_input, company_input, market_input],
                outputs=[market_input, market_hint_box],
            )

            company_input.change(
                fn=suggest_market_from_inputs,
                inputs=[ticker_input, company_input, market_input],
                outputs=[market_input, market_hint_box],
            )

            market_input.change(
                fn=suggest_market_from_inputs,
                inputs=[ticker_input, company_input, market_input],
                outputs=[market_input, market_hint_box],
            )

    return app


def launch() -> None:
    app = create_app()
    app.queue(default_concurrency_limit=2)
    app.launch(
        css=CUSTOM_CSS,
        server_name=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=_coerce_int(os.getenv("GRADIO_SERVER_PORT", "7860"), 7860),
        share=os.getenv("GRADIO_SHARE", "false").strip().lower() == "true",
    )


if __name__ == "__main__":
    launch()
