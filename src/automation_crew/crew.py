from __future__ import annotations

import os
from typing import List

from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from automation_crew.tools import (
    CompanyNewsSearchTool,
    GetCompanyInfoTool,
    GetCurrentStockPriceTool,
    GetFinancialStatementsTool,
)


@CrewBase
class AutomationCrew:
    """Investment Advisor crew."""

    agents: List[BaseAgent]
    tasks: List[Task]
    _shared_llm: LLM | None = None

    @staticmethod
    def _normalize_openrouter_model(model: str) -> str:
        normalized = model.strip()
        if not normalized:
            return normalized

        # LiteLLM expects explicit provider prefix to route correctly.
        # Accept user-friendly ids like "meta-llama/..." and normalize them.
        if normalized == "openrouter/free":
            return "openrouter/openrouter/free"

        if normalized.startswith("openrouter/"):
            return normalized

        return f"openrouter/{normalized}"

    def _create_llm(self) -> LLM:
        model = os.getenv("OPENROUTER_MODEL", "").strip()
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not model or not api_key:
            raise ValueError(
                "Missing OPENROUTER_MODEL or OPENROUTER_API_KEY. "
                "Set them in your environment before running the crew."
            )

        model = self._normalize_openrouter_model(model)

        return LLM(
            model=model,
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            temperature=0.2,
        )

    def _get_llm(self) -> LLM:
        if self._shared_llm is None:
            self._shared_llm = self._create_llm()
        return self._shared_llm

    @agent
    def news_info_explorer(self) -> Agent:
        return Agent(
            config=self.agents_config["news_info_explorer"],  # type: ignore[index]
            llm=self._get_llm(),
            tools=[CompanyNewsSearchTool()],
            verbose=True,
        )

    @agent
    def data_explorer(self) -> Agent:
        return Agent(
            config=self.agents_config["data_explorer"],  # type: ignore[index]
            llm=self._get_llm(),
            tools=[GetCompanyInfoTool(), GetFinancialStatementsTool()],
            verbose=True,
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["analyst"],  # type: ignore[index]
            llm=self._get_llm(),
            verbose=True,
        )

    @agent
    def fin_expert(self) -> Agent:
        return Agent(
            config=self.agents_config["fin_expert"],  # type: ignore[index]
            llm=self._get_llm(),
            tools=[GetCurrentStockPriceTool()],
            verbose=True,
        )

    @task
    def get_company_news(self) -> Task:
        return Task(
            config=self.tasks_config["get_company_news"],  # type: ignore[index]
        )

    @task
    def get_company_financials(self) -> Task:
        return Task(
            config=self.tasks_config["get_company_financials"],  # type: ignore[index]
        )

    @task
    def analyze_company(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_company"],  # type: ignore[index]
        )

    @task
    def advise_investment(self) -> Task:
        return Task(
            config=self.tasks_config["advise_investment"],  # type: ignore[index]
            output_file="report.md",
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
