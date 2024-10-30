import pytest
from click.testing import CliRunner

from autoopenraman.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_live_command(runner):

    result = runner.invoke(cli, ['live', '--debug'])
    assert result.exit_code == 0
    assert "Live mode" in result.output


def test_acq_command_no_args(runner):

    result = runner.invoke(cli, ['acq'])
    assert result.exit_code == 0
    assert "Acquisition mode" in result.output
