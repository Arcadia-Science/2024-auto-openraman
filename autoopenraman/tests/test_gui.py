import json
import sys
import tempfile
from pathlib import Path

import pytest
from pycromanager import Core, Studio
from PyQt5.QtWidgets import QApplication

from autoopenraman import config_profile
from autoopenraman.gui import AcquisitionWorker, AutoOpenRamanGUI


@pytest.fixture(scope="session")
def real_pycromanager():
    """
    Fixture for real pycromanager Core and Studio instances.

    Tests will use the actual MM Core and Studio, allowing for realistic testing
    with connected hardware. For CI/CD environments without MM, use pytest's
    --skip-mm flag to skip these tests.
    """
    try:
        core = Core()
        studio = Studio()

        # Initialize core for testing - this ensures we can acquire basic images
        # Only runs this setup once per session
        print("Setting up pycromanager Core")
        yield {"core": core, "studio": studio}

    except Exception as e:
        pytest.skip(f"Could not initialize pycromanager: {e}")

    print("Tearing down pycromanager Core")
    # No explicit cleanup needed for pycromanager


@pytest.fixture
def app():
    """Create a QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def gui_window(app, real_pycromanager):
    """Create a test instance of our GUI with debug mode enabled using real MM."""
    window = AutoOpenRamanGUI(debug=True)
    yield window
    window.close()


@pytest.fixture(autouse=True)
def setup_environment(request, monkeypatch):
    print("setup_environment")
    env_to_run = request.config.getoption("--environment")
    print(f"Setting up environment: {env_to_run}")

    # Create a temporary directory to use as save_dir
    temp_dir = tempfile.TemporaryDirectory()
    monkeypatch.setattr(config_profile, "save_dir", Path(temp_dir.name))

    # Initialize the profile
    config_profile.init_profile(env_to_run)

    # Yield the temp directory to keep it alive during the test
    yield temp_dir

    # Cleanup
    temp_dir.cleanup()


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


def _get_n_jsons_and_csvs_in_dir(directory: Path) -> tuple[int, int]:
    """Return the number of JSON and CSV files in the given directory."""
    n_jsons = len(list(directory.glob("*.json")))
    n_csvs = len(list(directory.glob("*.csv")))
    return n_jsons, n_csvs


def test_gui_initialization(gui_window):
    """Test that the GUI initializes properly with both modes available."""
    # Check title and main components
    assert gui_window.windowTitle() == "AutoOpenRaman"

    # Check that plot widget exists
    assert gui_window.plot_widget is not None
    assert gui_window.plot is not None

    # Check that both mode buttons exist
    assert gui_window.live_mode_btn is not None
    assert gui_window.acq_mode_btn is not None

    # Check that live mode is selected by default
    assert gui_window.live_mode_btn.isChecked() is True
    assert gui_window.acq_mode_btn.isChecked() is False
    assert gui_window.stacked_widget.currentIndex() == 0


def test_mode_switching(gui_window):
    """Test that switching between live and acquisition modes works."""
    # Start in live mode
    assert gui_window.stacked_widget.currentIndex() == 0

    # Switch to acquisition mode
    gui_window.acq_mode_btn.click()
    assert gui_window.live_mode_btn.isChecked() is False
    assert gui_window.acq_mode_btn.isChecked() is True
    assert gui_window.stacked_widget.currentIndex() == 1

    # Switch back to live mode
    gui_window.live_mode_btn.click()
    assert gui_window.live_mode_btn.isChecked() is True
    assert gui_window.acq_mode_btn.isChecked() is False
    assert gui_window.stacked_widget.currentIndex() == 0


def test_common_controls(gui_window):
    """Test that common controls are properly initialized."""
    # Check that controls exist
    assert gui_window.reverse_x_check is not None
    assert gui_window.median_filter_check is not None
    assert gui_window.kernel_size_input is not None

    # Check default state
    assert gui_window.reverse_x_check.isChecked() is False
    assert gui_window.median_filter_check.isChecked() is False
    assert gui_window.kernel_size_input.text() == "3"


def test_live_mode_controls(gui_window):
    """Test that live mode controls are properly initialized."""
    # Check that live mode controls exist
    assert gui_window.start_live_btn is not None
    assert gui_window.stop_live_btn is not None

    # Check default state
    assert gui_window.start_live_btn.isEnabled() is True
    assert gui_window.stop_live_btn.isEnabled() is False


def test_acquisition_mode_controls(gui_window):
    """Test that acquisition mode controls are properly initialized."""
    # Switch to acquisition mode
    gui_window.acq_mode_btn.click()

    # Check that acquisition mode controls exist
    assert gui_window.position_file_input is not None
    assert gui_window.browse_pos_btn is not None
    assert gui_window.exp_dir_input is not None
    assert gui_window.browse_dir_btn is not None
    assert gui_window.n_averages_input is not None
    assert gui_window.shutter_check is not None
    assert gui_window.randomize_check is not None
    assert gui_window.start_acq_btn is not None

    # Check default state
    assert gui_window.position_file_input.text() == ""
    assert gui_window.exp_dir_input.text() == ""
    assert gui_window.n_averages_input.value() == 1
    assert gui_window.shutter_check.isChecked() is False
    assert gui_window.randomize_check.isChecked() is False


def test_spectrum_processing(gui_window):
    """Test that spectrum processing works correctly."""
    import numpy as np

    # Create a test spectrum
    test_spectrum = np.ones(100)

    # Test with default settings (no processing)
    result = gui_window.process_spectrum(test_spectrum)
    assert np.array_equal(result, test_spectrum)

    # Test with reverse X enabled
    gui_window.reverse_x = True
    result = gui_window.process_spectrum(test_spectrum)
    assert result[0] == test_spectrum[-1]
    assert result[-1] == test_spectrum[0]

    # Reset and test with median filter
    gui_window.reverse_x = False
    gui_window.apply_median_filter = True

    # Create a test spectrum with a spike
    test_spectrum_with_spike = np.ones(100)
    test_spectrum_with_spike[50] = 100

    result = gui_window.process_spectrum(test_spectrum_with_spike)
    # The spike should be smoothed out by the median filter
    assert result[50] < 100


# Tests adapted from test_acq.py
def test_acq_worker_no_args(app, real_pycromanager):
    """Test acquisition worker with default settings."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "exp1"
        exp_path.mkdir()

        # Create acquisition worker with real MM
        worker = AcquisitionWorker(
            n_averages=1,
            exp_path=exp_path,
            position_file=None,
            shutter=False,
            randomize_stage_positions=False,
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory and files
        assert exp_path.is_dir()
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == 1
        assert n_csvs == 1


def test_acq_worker_with_averaging(app, real_pycromanager):
    """Test acquisition worker with averaging."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "exp1"
        exp_path.mkdir()

        # Create acquisition worker
        worker = AcquisitionWorker(
            n_averages=5,
            exp_path=exp_path,
            position_file=None,
            shutter=False,
            randomize_stage_positions=False,
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory and files
        assert exp_path.is_dir()
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == 1
        assert n_csvs == 1


def test_acq_worker_with_position_file(app, real_pycromanager):
    """Test acquisition worker with position file."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "exp1"
        exp_path.mkdir()

        # Create a mock position file
        _n_positions = 5
        position_file = Path(temp_dir) / "positions.json"
        _create_mock_position_file(position_file, n_positions=_n_positions)

        # Create acquisition worker
        worker = AcquisitionWorker(
            n_averages=2,
            exp_path=exp_path,
            position_file=str(position_file),
            shutter=False,
            randomize_stage_positions=False,
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory and files
        assert exp_path.is_dir()
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == _n_positions
        assert n_csvs == _n_positions


def test_acq_worker_with_shutter(app, real_pycromanager):
    """Test acquisition worker with shutter."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "exp1"
        exp_path.mkdir()

        # Create acquisition worker
        worker = AcquisitionWorker(
            n_averages=1,
            exp_path=exp_path,
            position_file=None,
            shutter=True,
            randomize_stage_positions=False,
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory and files
        assert exp_path.is_dir()
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == 1
        assert n_csvs == 1


def test_acq_worker_with_timelapse(app, real_pycromanager):
    """Test acquisition worker with timelapse."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "timelapse"
        exp_path.mkdir()

        # Create acquisition worker
        worker = AcquisitionWorker(
            n_averages=1,
            exp_path=exp_path,
            position_file=None,
            shutter=False,
            randomize_stage_positions=False,
            num_time_points=3,
            time_interval_s=0.1,  # Short interval for testing
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory exists
        assert exp_path.is_dir()

        # Should have 3 time points with JSON/CSV pairs
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == 3
        assert n_csvs == 3


def test_acq_worker_with_timelapse_and_position_file(app, real_pycromanager):
    """Test acquisition worker with timelapse and position file."""
    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as temp_dir:
        exp_path = Path(temp_dir) / "timelapse_positions"
        exp_path.mkdir()

        # Create a mock position file
        _n_positions = 3
        position_file = Path(temp_dir) / "positions.json"
        _create_mock_position_file(position_file, n_positions=_n_positions)

        # Create acquisition worker
        worker = AcquisitionWorker(
            n_averages=1,
            exp_path=exp_path,
            position_file=str(position_file),
            shutter=False,
            randomize_stage_positions=False,
            num_time_points=3,
            time_interval_s=0.1,  # Short interval for testing
        )

        # Run acquisition
        worker.run_acquisition()

        # Verify the output directory exists
        assert exp_path.is_dir()

        # Should have 3 time points for each position
        n_jsons, n_csvs = _get_n_jsons_and_csvs_in_dir(exp_path)
        assert n_jsons == 9  # 3 positions × 3 time points
        assert n_csvs == 9
