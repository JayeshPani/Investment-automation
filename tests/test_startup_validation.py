from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from automation_crew.main import validate_runtime_environment  # noqa: E402


class StartupValidationTests(TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_provider_env_vars_raise_clear_error(self):
        with self.assertRaises(ValueError) as exc:
            validate_runtime_environment({"ticker": "MS", "company_name": "Morgan Stanley"})

        message = str(exc.exception)
        self.assertIn("OPENROUTER_API_KEY", message)
        self.assertIn("OPENROUTER_MODEL", message)

    @patch.dict(
        os.environ,
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "openrouter/free-model",
        },
        clear=True,
    )
    def test_missing_company_input_raises_clear_error(self):
        with self.assertRaises(ValueError) as exc:
            validate_runtime_environment({"ticker": "", "company_name": ""})

        message = str(exc.exception)
        self.assertIn("COMPANY_TICKER", message)
        self.assertIn("COMPANY_NAME", message)

    @patch.dict(
        os.environ,
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "openrouter/free-model",
        },
        clear=True,
    )
    def test_valid_configuration_passes(self):
        validate_runtime_environment({"ticker": "MS", "company_name": "Morgan Stanley"})
