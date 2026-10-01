import pytest

from candlestack.cli import main


def test_without_a_command_prints_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: candlestack-bt")
    assert "run" in out


def test_help_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    assert "Backtest a model's predictions on candles." in capsys.readouterr().out


def test_unknown_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["walk"])

    assert exit_info.value.code == 2
    # Newer 3.13 releases quote the choices that follow, (choose from 'run'); older ones do not.
    assert "argument command: invalid choice: 'walk'" in capsys.readouterr().err
