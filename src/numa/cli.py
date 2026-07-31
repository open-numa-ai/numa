"""Command-line interface for bootstrapping and running Numa agents."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import yaml

from numa.agents import EchoAgent
from numa.config import NumaConfig
from numa.core import Task
from numa.runtime import AgentRuntime
from numa.utils import configure_logging

_AGENT_FACTORIES = {"example_agent": EchoAgent}


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="numa", description="Numa agent framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a starter numa.yaml")
    init_parser.add_argument("directory", nargs="?", default=".", type=Path)

    run_parser = subparsers.add_parser("run", help="run a registered agent")
    run_parser.add_argument("agent", choices=sorted(_AGENT_FACTORIES))
    run_parser.add_argument("--task", default="Hello from Numa")
    run_parser.add_argument("--config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Numa command-line interface."""
    args = build_parser().parse_args(argv)

    if args.command == "init":
        return _init_project(args.directory)
    if args.command == "run":
        return _run_agent(args.agent, args.task, args.config)
    return 1


def _init_project(directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "numa.yaml"
    if config_path.exists():
        print(f"Configuration already exists: {config_path}")
        return 1

    config = NumaConfig()
    config_path.write_text(yaml.safe_dump(config.to_dict(), sort_keys=False), encoding="utf-8")
    print(f"Created {config_path}")
    return 0


def _run_agent(agent_name: str, task_description: str, config_path: Path | None) -> int:
    config = NumaConfig.load(config_path)
    configure_logging(config.logging.level, config.logging.format)

    agent = _AGENT_FACTORIES[agent_name]()
    result = AgentRuntime().run(agent, Task(description=task_description))
    print(result.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
