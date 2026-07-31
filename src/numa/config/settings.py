"""Typed configuration loading from defaults, files, and environment variables."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from numa.core import ConfigurationError


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Logging settings for the Numa namespace."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Limits used by current and future runtime implementations."""

    max_steps: int = 10


@dataclass(frozen=True, slots=True)
class NumaConfig:
    """Top-level Numa configuration."""

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> NumaConfig:
        """Load configuration, with environment variables taking precedence."""
        data = _load_file(Path(path)) if path is not None else {}
        environment = os.environ if environ is None else environ

        logging_data = _mapping(data.get("logging"), "logging")
        runtime_data = _mapping(data.get("runtime"), "runtime")

        level = environment.get("NUMA_LOG_LEVEL", logging_data.get("level", "INFO"))
        log_format = environment.get(
            "NUMA_LOG_FORMAT",
            logging_data.get("format", LoggingConfig().format),
        )
        max_steps_value: object = environment.get(
            "NUMA_RUNTIME_MAX_STEPS",
            runtime_data.get("max_steps", 10),
        )

        try:
            max_steps = int(str(max_steps_value))
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("runtime.max_steps must be an integer") from exc

        if max_steps < 1:
            raise ConfigurationError("runtime.max_steps must be greater than zero")

        return cls(
            logging=LoggingConfig(level=str(level).upper(), format=str(log_format)),
            runtime=RuntimeConfig(max_steps=max_steps),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of this configuration."""
        return asdict(self)


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {path}")

    try:
        with path.open(encoding="utf-8") as config_file:
            if path.suffix.lower() == ".json":
                data: object = json.load(config_file)
            elif path.suffix.lower() in {".yaml", ".yml"}:
                data = yaml.safe_load(config_file)
            else:
                raise ConfigurationError("Configuration file must be JSON or YAML")
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not load configuration: {path}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be a mapping")
    return cast(dict[str, Any], data)


def _mapping(value: object, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a mapping")
    return cast(dict[str, Any], value)
