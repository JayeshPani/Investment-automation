# Investment Advisor Crew

4-agent CrewAI workflow for company investment research.

## What It Does

This crew runs four specialized agents:

1. `news_info_explorer`: collects recent news using Exa with domain-priority
   logic (`reuters.com`, `bloomberg.com`, `wsj.com`), then broad fallback.
2. `data_explorer`: fetches structured fundamentals and statement highlights
   using `yfinance`.
3. `analyst`: merges the two upstream outputs into a detailed thesis.
4. `fin_expert`: produces a risk-scored recommendation with confidence and
   horizon views.

The first two tasks run in parallel (`async_execution: true`), then fan in to
analysis and final advice.

## Setup

1. Ensure Python `>=3.10,<3.14`.
2. Install dependencies:

```bash
crewai install
```

3. Create your `.env` from `.env.example` and set values:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (env-driven free model strategy)
- `COMPANY_TICKER`
- `COMPANY_NAME`

Optional:

- `OPENROUTER_BASE_URL` (defaults to `https://openrouter.ai/api/v1`)
- `OPENROUTER_MODEL_FALLBACKS` (comma-separated fallback models used by GUI when the primary model is rate-limited)
- `EXA_API_KEY` (optional; only needed if you want direct Exa API mode instead of Docker MCP fallback)
- `MARKET` (`global` or `india`; default `global`)
- `EXCHANGE_PREFERENCE` (`NSE` or `BSE`; used when `MARKET=india`)
- `INVESTOR_PROFILE` (default `moderate`)
- `ANALYSIS_HORIZON_DAYS` (default `365`)
- `NEWS_LOOKBACK_DAYS` (default `30`)

Indian market notes:
- If `MARKET=india` and ticker is provided without suffix (for example `RELIANCE`),
  the runtime auto-normalizes it to `RELIANCE.NS` (or `.BO` when `EXCHANGE_PREFERENCE=BSE`).
- India mode prioritizes India-focused financial news domains before broad fallback.

## Run

```bash
crewai run
```

Output is written to `report.md`.

## Run GUI (Gradio)

```bash
crewai install
run_gui
```

Open `http://127.0.0.1:7860` in your browser.

GUI features:
- form inputs for ticker, company, profile, horizon, and news lookback
- market selector (`global`/`india`) and exchange preference (`NSE`/`BSE`)
- one-click run of the full 4-agent pipeline
- live status, extracted recommendation fields, and full markdown report
- downloadable `report.md`

Optional GUI env vars:
- `GRADIO_SERVER_NAME` (default `127.0.0.1`)
- `GRADIO_SERVER_PORT` (default `7860`)
- `GRADIO_SHARE` (`true`/`false`, default `false`)
- `GUI_RATE_LIMIT_RETRIES` (default `3`; retries on `429`/rate-limit errors)

## Expected Final Report Sections

The advisor task enforces these sections:

- `Decision (Invest/Do Not Invest/Hold)`
- `Confidence (0-100)`
- `Time Horizon View (30/90/365 days)`
- `Bull Case`
- `Bear Case`
- `Key Risks`
- `Risk Controls`
- `Data Gaps`
- `Disclaimer`

Disclaimer includes: `This is informational analysis, not financial advice.`

## Notes

- Model selection is fully env-driven via `OPENROUTER_MODEL`.
- The project intentionally avoids hardcoded model IDs.
- `OPENROUTER_MODEL=openrouter/free` is supported and auto-normalized for
  LiteLLM/OpenRouter compatibility at runtime.
- News search uses Docker MCP Exa by default when `EXA_API_KEY` is not set.
- If priority-domain news coverage is sparse, fallback to broader web is used
  and source confidence is downgraded.
- GUI run path retries provider `429` responses with backoff and can auto-switch
  to models listed in `OPENROUTER_MODEL_FALLBACKS`.

## Troubleshooting

- If Docker MCP is unavailable in your environment, set `EXA_API_KEY` to use
  direct Exa API mode instead of Docker MCP fallback.
