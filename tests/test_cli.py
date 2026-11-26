"""CLI smoke tests using Typer CliRunner."""

from typer.testing import CliRunner

from humanlens.cli import app

runner = CliRunner()


def test_cli_version_and_models():
    r1 = runner.invoke(app, ["version"])
    assert r1.exit_code == 0
    assert "humanlens" in r1.stdout

    r2 = runner.invoke(app, ["models"])
    assert r2.exit_code == 0
    assert "fakespot" in r2.stdout


def test_cli_scan_and_humanize_fast():
    r1 = runner.invoke(
        app,
        ["scan", "Furthermore, it is crucial to leverage robust solutions today.", "--fast"],
    )
    assert r1.exit_code == 0
    assert "HumanLens Analysis" in r1.stdout

    r2 = runner.invoke(
        app,
        ["humanize", "Furthermore, it is crucial to leverage robust solutions.", "--fast"],
    )
    assert r2.exit_code == 0
    assert "Humanizer Comparison" in r2.stdout
