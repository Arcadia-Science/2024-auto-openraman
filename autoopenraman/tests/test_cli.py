import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autoopenraman.cli import cli


def _get_n_jsons_and_csvs_in_dir(directory: Path) -> tuple[int, int]:
    """Return the number of JSON and CSV files in the given directory."""
    n_jsons = len(list(directory.glob("*.json")))
    n_csvs = len(list(directory.glob("*.csv")))
    return n_jsons, n_csvs


@pytest.fixture
def runner():
    return CliRunner()


def test_live_command(runner):
    result = runner.invoke(cli, ["live", "--debug"])
    assert result.exit_code == 0
    assert "Live mode" in result.output


def test_acq_command_no_args(runner):
    result = runner.invoke(cli, ["acq"])
    assert result.exit_code == 0
    assert "Acquisition mode" in result.output


def test_acq_command_with_averaging(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["acq", "--n-averages", "5", "--save-dir", "test_data"])
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        # Verify the output directory and files
        save_dir = Path("test_data")
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 1
        assert n_csvs == 1


def _create_mock_position_file(file_path: Path, n_positions: int = 2) -> None:
    """
    Create a mock JSON file with stage positions for testing.

    Parameters:
        file_path (Path): The path to the JSON file to create
        n_positions (int): The number of positions to create
    """
    mock_data = {
        "map": {
            "StagePositions": {
                "array": [
                    {
                        "DevicePositions": {
                            "array": [
                                {"Position_um": {"array": [10.0 * i, 20.0 * i]}},
                            ]
                        },
                        "Label": {"scalar": f"Position{i+1}"},
                    }
                    for i in range(n_positions)
                ]
            }
        }
    }

    with open(file_path, "w") as file:
        json.dump(mock_data, file, indent=4)


def test_acq_command_with_position_file(runner):
    with runner.isolated_filesystem():
        _n_positions = 5
        position_file = Path("positions.json")
        _create_mock_position_file(position_file, n_positions=_n_positions)
        result = runner.invoke(
            cli, ["acq", "--n-averages", "5", "--position_file", str(position_file)]
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        # Verify the AcquisitionManager behavior
        save_dir = Path("data/")
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == _n_positions
    assert n_csvs == _n_positions


def test_acq_command_with_shutter(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli, ["acq", "--shutter", "White Light Shutter", "--save-dir", "test_data"]
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output
        assert "Shutter open" in result.output
        assert "Shutter closed" in result.output

        # Verify the output directory and files
        save_dir = Path("test_data")
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 1
        assert n_csvs == 1


def test_acq_command_with_badshuttername(runner):
    with runner.isolated_filesystem():
        _n_positions = 3
        position_file = Path("positions.json")
        _create_mock_position_file(position_file, n_positions=_n_positions)
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "5",
                "--position_file",
                str(position_file),
                "--shutter",
                "Bad shutter",
            ],
        )
        assert result.exit_code == 1


def test_acq_command_with_shutter_and_position_file(runner):
    with runner.isolated_filesystem():
        _n_positions = 3
        position_file = Path("positions.json")
        _create_mock_position_file(position_file, n_positions=_n_positions)
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "5",
                "--position_file",
                str(position_file),
                "--shutter",
                "White Light Shutter",
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output
        assert "Shutter open" in result.output
        assert "Shutter closed" in result.output

        # Verify the AcquisitionManager behavior
        save_dir = Path("data/")
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == _n_positions
        assert n_csvs == _n_positions
