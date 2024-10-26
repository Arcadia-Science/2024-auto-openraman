import pytest
from click.testing import CliRunner

from autoopenraman.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_live_command(runner):
    """Test live command"""
    result = runner.invoke(cli, ['live'])
    assert result.exit_code == 0
    assert "Live mode" in result.output


def test_acq_command_without_pos_filepath(runner):
    """Test acq command with default arguments"""
    result = runner.invoke(cli, ['acq'])
    assert result.exit_code == 0
    assert "Acquisition mode" in result.output
