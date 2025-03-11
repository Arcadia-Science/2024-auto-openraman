import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autoopenraman import config_profile
from autoopenraman.cli import cli


def _get_n_jsons_and_csvs_in_dir(directory: Path) -> tuple[int, int]:
    """Return the number of JSON and CSV files in the given directory."""
    n_jsons = len(list(directory.glob("*.json")))
    n_csvs = len(list(directory.glob("*.csv")))
    return n_jsons, n_csvs


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def setup_environment(request):
    print("setup_environment")
    env_to_run = request.config.getoption("--environment")
    print(f"Setting up environment: {env_to_run}")
    config_profile.init_profile(env_to_run)


def test_acq_command_no_args(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["acq"])
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output


def test_acq_command_with_averaging(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["acq", "--n-averages", "5", "--exp-dir", "exp1"])
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        # Verify the output directory and files
        save_dir = config_profile.save_dir / "exp1"
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
            cli,
            [
                "acq",
                "--n-averages",
                "5",
                "--position_file",
                str(position_file),
                "--exp-dir",
                "exp1",
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        save_dir = config_profile.save_dir / "exp1"
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == _n_positions
        assert n_csvs == _n_positions


def test_acq_command_with_shutter(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["acq", "--shutter", "--exp-dir", "exp1"])
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output
        assert "Shutter open" in result.output
        assert "Shutter closed" in result.output

        # Verify the output directory and files
        save_dir = config_profile.save_dir / "exp1"
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 1
        assert n_csvs == 1


def test_acq_command_with_bad_shutter_name(runner):
    with runner.isolated_filesystem():
        config_profile.shutter_name = "Bad shutter"
        _n_positions = 3
        position_file = Path("positions.json")
        _create_mock_position_file(position_file, n_positions=_n_positions)
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "5",
                "--shutter",
            ],
        )
        assert result.exit_code == 1
        assert "No device" in result.exception.args[0]


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
                "--exp-dir",
                "exp1",
                "--position_file",
                str(position_file),
                "--shutter",
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output
        assert "Shutter open" in result.output
        assert "Shutter closed" in result.output

        # Verify the output directory and files
        save_dir = config_profile.save_dir / "exp1"
        assert save_dir.is_dir()

        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == _n_positions
        assert n_csvs == _n_positions


def test_acq_command_with_timelapse(runner):
    """Test acquisition with time series (timelapse)."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "2",
                "--exp-dir",
                "timelapse",
                "--num_time_points",
                "3",
                "--time_interval_s",
                "0.1",  # Short interval for testing
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        # Verify the output directory exists
        save_dir = config_profile.save_dir / "timelapse"
        assert save_dir.is_dir()

        # Should have 3 time points with JSON/CSV pairs
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 3
        assert n_csvs == 3

        # Check for time point naming in files
        files = list(save_dir.glob("*.csv"))
        time_point_patterns = [f"time_{i}" for i in range(3)]
        for pattern in time_point_patterns:
            assert any(pattern in f.name for f in files), f"Missing file with {pattern}"


def test_acq_command_with_timelapse_and_shutter(runner):
    """Test acquisition with time series and shutter control."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "2",
                "--exp-dir",
                "timelapse_shutter",
                "--num_time_points",
                "2",
                "--time_interval_s",
                "0.1",
                "--shutter",
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output
        assert "Shutter open" in result.output
        assert "Shutter closed" in result.output

        # Verify the output directory exists
        save_dir = config_profile.save_dir / "timelapse_shutter"
        assert save_dir.is_dir()

        # Should have 2 time points with JSON/CSV pairs
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 2
        assert n_csvs == 2


def test_acq_command_timelapse_with_position_file(runner):
    """Test acquisition with time series and stage positions."""
    with runner.isolated_filesystem():
        _n_positions = 3
        position_file = Path("positions.json")
        _create_mock_position_file(position_file, n_positions=_n_positions)
        result = runner.invoke(
            cli,
            [
                "acq",
                "--n-averages",
                "2",
                "--exp-dir",
                "timelapse_positions",
                "--num_time_points",
                "3",
                "--time_interval_s",
                "0.1",
                "--position_file",
                str(position_file),
            ],
        )
        assert result.exit_code == 0
        assert "Acquisition mode" in result.output

        # Verify the output directory exists
        save_dir = config_profile.save_dir / "timelapse_positions"
        assert save_dir.is_dir()

        # Should have 3 time points with JSON/CSV pairs
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(save_dir)
        assert n_jsons == 9
        assert n_csvs == 9

        # Check for time point naming in files
        files = list(save_dir.glob("*.csv"))
        time_point_patterns = [f"time_{i}" for i in range(3)]
        for pattern in time_point_patterns:
            assert any(pattern in f.name for f in files), f"Missing file with {pattern}"
