from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Type

from crewai.tools import BaseTool
from crewai_tools import EXASearchTool
from pydantic import BaseModel, Field, PrivateAttr


class CompanyNewsSearchInput(BaseModel):
    """Input schema for company news search."""

    ticker: str = Field(..., description="Public ticker symbol, e.g., MS")
    company_name: str = Field(..., description="Company name, e.g., Morgan Stanley")
    lookback_days: int = Field(
        30,
        description="How many days back to search for news",
        ge=1,
        le=365,
    )
    market: str = Field(
        default="",
        description="Optional market context. Use 'india' for NSE/BSE focused sources.",
    )


class CompanyNewsSearchTool(BaseTool):
    """Search company news with source-priority fallback logic."""

    name: str = "company_news_search"
    description: str = (
        "Find recent company news. Prioritizes Reuters/Bloomberg/WSJ first, "
        "then falls back to broader web results if coverage is insufficient."
    )
    args_schema: Type[BaseModel] = CompanyNewsSearchInput

    minimum_priority_results: int = 3
    _global_priority_domains: tuple[str, ...] = PrivateAttr(
        default=("reuters.com", "bloomberg.com", "wsj.com")
    )
    _india_priority_domains: tuple[str, ...] = PrivateAttr(
        default=(
            "economictimes.indiatimes.com",
            "moneycontrol.com",
            "livemint.com",
            "business-standard.com",
            "reuters.com",
        )
    )
    _exa_tool: EXASearchTool | None = PrivateAttr(default=None)

    @staticmethod
    def _normalize_market(market: str, ticker: str) -> str:
        value = (market or "").strip().lower()
        if not value:
            value = os.getenv("MARKET", "global").strip().lower()

        if ticker.endswith(".NS") or ticker.endswith(".BO"):
            return "india"
        if value in {"india", "indian", "nse", "bse", "in"}:
            return "india"
        return "global"

    def _priority_domains_for_market(self, market: str) -> tuple[str, ...]:
        if market == "india":
            return self._india_priority_domains
        return self._global_priority_domains

    def _get_exa_tool(self) -> EXASearchTool:
        if self._exa_tool is not None:
            return self._exa_tool

        # Avoid EXASearchTool interactive install prompt and fail with clear guidance.
        try:
            import exa_py  # noqa: F401
        except ImportError as exc:  # pragma: no cover - import path guard
            raise RuntimeError(
                "Missing dependency 'exa_py'. Install project dependencies to use news search."
            ) from exc

        self._exa_tool = EXASearchTool(content=True, summary=True)
        return self._exa_tool

    @staticmethod
    def _parse_dockermcp_json(raw_text: str) -> dict[str, Any]:
        # Docker MCP prefixes JSON with "Tool call took: ...", so parse from first "{"
        json_start = raw_text.find("{")
        if json_start == -1:
            raise ValueError("Could not parse DockerMCP tool output as JSON.")
        return json.loads(raw_text[json_start:])

    def _run_dockermcp_exa_search(self, query: str) -> list[dict[str, str]]:
        command = [
            "docker",
            "mcp",
            "tools",
            "call",
            "web_search_exa",
            f"query={query}",
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Docker CLI not found. Install Docker Desktop to use DockerMCP Exa fallback."
            ) from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(
                f"DockerMCP Exa search failed: {message or 'unknown error'}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("DockerMCP Exa search timed out.") from exc

        payload = self._parse_dockermcp_json(result.stdout)
        return self._normalize_results(payload)

    @staticmethod
    def _safe_str(value: Any) -> str:
        if value is None:
            return "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    def _normalize_results(self, raw_results: Any) -> list[dict[str, str]]:
        if raw_results is None:
            return []

        if isinstance(raw_results, dict):
            records = raw_results.get("results", [])
        else:
            records = getattr(raw_results, "results", [])

        normalized: list[dict[str, str]] = []
        for item in records:
            if isinstance(item, dict):
                title = item.get("title")
                url = item.get("url")
                published_date = item.get("published_date") or item.get("publishedDate")
                summary = item.get("summary") or item.get("text")
            else:
                title = getattr(item, "title", None)
                url = getattr(item, "url", None)
                published_date = getattr(item, "published_date", None) or getattr(
                    item, "publishedDate", None
                )
                summary = getattr(item, "summary", None) or getattr(item, "text", None)

            normalized.append(
                {
                    "title": self._safe_str(title),
                    "url": self._safe_str(url),
                    "published_date": self._safe_str(published_date),
                    "summary": self._safe_str(summary)[:500],
                }
            )

        return normalized

    @staticmethod
    def _deduplicate_articles(articles: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()

        for article in articles:
            key = article.get("url", "N/A")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(article)

        return deduped

    def _run(
        self,
        ticker: str,
        company_name: str,
        lookback_days: int = 30,
        market: str = "",
    ) -> str:
        ticker_value = ticker.strip().upper()
        company_name_value = company_name.strip()
        market_value = self._normalize_market(market, ticker_value)
        priority_domains = self._priority_domains_for_market(market_value)
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
        ).date().isoformat()

        if market_value == "india":
            base_query = (
                f"{company_name_value} ({ticker_value}) latest earnings guidance outlook "
                "NSE BSE India INR rupee regulation SEBI RBI risks capital allocation"
            )
        else:
            base_query = (
                f"{company_name_value} ({ticker_value}) latest earnings guidance outlook "
                "regulatory risks capital allocation"
            )

        priority_query = f"{base_query} (" + " OR ".join(
            f"site:{domain}" for domain in priority_domains
        ) + ")"

        use_direct_exa = bool(os.getenv("EXA_API_KEY", "").strip())
        backend = "direct_exa_api" if use_direct_exa else "dockermcp_exa_tool"

        if use_direct_exa:
            tool = self._get_exa_tool()
            priority_raw = tool._run(
                search_query=base_query,
                start_published_date=start_date,
                include_domains=list(priority_domains),
            )
            priority_articles = self._normalize_results(priority_raw)
        else:
            priority_articles = self._run_dockermcp_exa_search(priority_query)

        fallback_used = len(priority_articles) < self.minimum_priority_results
        source_confidence = "high"
        broad_articles: list[dict[str, str]] = []
        data_quality_notes: list[str] = []

        if fallback_used:
            if use_direct_exa:
                tool = self._get_exa_tool()
                broad_raw = tool._run(
                    search_query=base_query,
                    start_published_date=start_date,
                )
                broad_articles = self._normalize_results(broad_raw)
            else:
                broad_articles = self._run_dockermcp_exa_search(base_query)
            source_confidence = "medium"
            data_quality_notes.append(
                "Priority-domain coverage was limited; broad web fallback was used."
            )

        articles = self._deduplicate_articles(priority_articles + broad_articles)[:15]

        if not articles:
            source_confidence = "low"
            data_quality_notes.append("No recent news articles were returned by Exa.")

        payload = {
            "ticker": ticker_value,
            "company_name": company_name_value,
            "market": market_value,
            "lookback_days": int(lookback_days),
            "query": base_query,
            "priority_domains": list(priority_domains),
            "priority_results_count": len(priority_articles),
            "total_results_count": len(articles),
            "fallback_used": fallback_used,
            "news_backend": backend,
            "source_confidence": source_confidence,
            "articles": articles,
            "data_quality_notes": data_quality_notes,
        }

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
