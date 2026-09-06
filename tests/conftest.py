from __future__ import annotations

from pathlib import Path

import pytest

from src.config_loader import load_config


@pytest.fixture(scope="session")
def config():
    return load_config(Path(__file__).parents[1] / "config")
