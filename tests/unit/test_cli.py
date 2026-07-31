from pathlib import Path

from pytest import CaptureFixture

from numa.cli import main


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
