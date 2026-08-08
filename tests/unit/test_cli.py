from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

from numa.agents import Agent, EchoAgent
from numa.cli import build_parser, main
from numa.plugins import AGENT_PLUGIN_GROUP, Plugin


def test_help_describes_numa_as_an_agent_runtime() -> None:
    assert build_parser().description == "Numa provider-neutral runtime for agent applications"


def test_init_creates_default_config(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    assert main(["init", str(tmp_path)]) == 0

    config_path = tmp_path / "numa.yaml"
    assert config_path.is_file()
    assert "Created" in capsys.readouterr().out


def test_init_does_not_overwrite_config(tmp_path: Path) -> None:
    config_path = tmp_path / "numa.yaml"
    config_path.write_text("existing: true\n", encoding="utf-8")

    assert main(["init", str(tmp_path)]) == 1
    assert config_path.read_text(encoding="utf-8") == "existing: true\n"


def test_run_example_agent(capsys: CaptureFixture[str]) -> None:
    assert main(["run", "example_agent", "--task", "hello"]) == 0
    assert capsys.readouterr().out == "hello\n"


def test_list_builtin_plugins(capsys: CaptureFixture[str]) -> None:
    assert main(["plugins", "list"]) == 0

    output = capsys.readouterr().out.splitlines()
    assert "agent\texample_agent" in output
    assert "tool\tadd" in output


def test_list_plugins_by_type(capsys: CaptureFixture[str]) -> None:
    assert main(["plugins", "list", "--type", "agent"]) == 0

    output = capsys.readouterr().out
    assert "agent\texample_agent" in output
    assert "tool\t" not in output


def test_run_unknown_agent_returns_plugin_error(capsys: CaptureFixture[str]) -> None:
    assert main(["run", "missing"]) == 2
    assert "not installed" in capsys.readouterr().err


def test_run_discovered_agent(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    plugin = Plugin(
        name="example_agent",
        group=AGENT_PLUGIN_GROUP,
        component_type=Agent,  # type: ignore[type-abstract]
        _load_factory=lambda: EchoAgent,
    )
    monkeypatch.setattr("numa.cli.discover_agents", lambda: {"example_agent": plugin})

    assert main(["run", "example_agent", "--task", "from plugin"]) == 0
    assert capsys.readouterr().out == "from plugin\n"


def test_listing_does_not_load_plugin(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def failed_loader() -> object:
        raise RuntimeError("must not load")

    plugin = Plugin(
        name="broken",
        group=AGENT_PLUGIN_GROUP,
        component_type=Agent,  # type: ignore[type-abstract]
        _load_factory=failed_loader,
    )
    monkeypatch.setattr("numa.cli.discover_agents", lambda: {"broken": plugin})

    assert main(["plugins", "list", "--type", "agent"]) == 0
    assert capsys.readouterr().out == "agent\tbroken\n"
