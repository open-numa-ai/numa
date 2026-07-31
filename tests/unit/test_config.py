import json
from pathlib import Path

import pytest

from numa.config import NumaConfig
from numa.core import ConfigurationError


def test_loads_json_and_environment_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "numa.json"
    config_path.write_text(
        json.dumps({"logging": {"level": "WARNING"}, "runtime": {"max_steps": 4}}),
        encoding="utf-8",
    )

    config = NumaConfig.load(
        config_path,
        environ={"NUMA_LOG_LEVEL": "DEBUG", "NUMA_RUNTIME_MAX_STEPS": "8"},
    )

    assert config.logging.level == "DEBUG"
    assert config.runtime.max_steps == 8


def test_loads_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "numa.yaml"
    config_path.write_text("runtime:\n  max_steps: 3\n", encoding="utf-8")

    assert NumaConfig.load(config_path, environ={}).runtime.max_steps == 3


def test_rejects_invalid_max_steps() -> None:
    with pytest.raises(ConfigurationError, match="greater than zero"):
        NumaConfig.load(environ={"NUMA_RUNTIME_MAX_STEPS": "0"})
