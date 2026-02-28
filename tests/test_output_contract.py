from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class OutputContractTests(TestCase):
    def test_advice_expected_output_contains_required_sections(self):
        tasks_file = Path(__file__).resolve().parents[1] / "src" / "automation_crew" / "config" / "tasks.yaml"
        config = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))

        expected = config["advise_investment"]["expected_output"]

        required_sections = [
            "Decision (Invest/Do Not Invest/Hold)",
            "Confidence (0-100)",
            "Time Horizon View (30/90/365 days)",
            "Bull Case",
            "Bear Case",
            "Key Risks",
            "Risk Controls",
            "Data Gaps",
            "Disclaimer",
            "This is informational analysis, not financial advice.",
        ]

        for section in required_sections:
            self.assertIn(section, expected)

    def test_advice_expected_output_contains_advanced_sections(self):
        tasks_file = Path(__file__).resolve().parents[1] / "src" / "automation_crew" / "config" / "tasks.yaml"
        config = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))

        expected = config["advise_investment"]["expected_output"]

        advanced_sections = [
            "Investment Scorecard",
            "Metrics Used in Decision",
            "Evidence Table",
            "Assumptions Ledger",
            "Catalyst Timeline",
            "Monitoring Triggers",
        ]

        for section in advanced_sections:
            self.assertIn(section, expected)

    def test_analyze_expected_output_contains_institutional_sections(self):
        tasks_file = Path(__file__).resolve().parents[1] / "src" / "automation_crew" / "config" / "tasks.yaml"
        config = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))

        expected = config["analyze_company"]["expected_output"]

        required_sections = [
            "Executive Summary",
            "Investment Scorecard",
            "News Synthesis",
            "Financial Analysis",
            "Integrated Thesis",
            "Scenario Analysis",
            "Evidence Table",
            "Assumptions Ledger",
            "Key Risks",
            "Data Gaps",
        ]

        for section in required_sections:
            self.assertIn(section, expected)
