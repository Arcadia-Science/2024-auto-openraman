# Mock the pycromanager dependencies
import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from autoopenraman.gui import AutoOpenRamanGUI


# Create patch for Core and Studio
@pytest.fixture(autouse=True)
def mock_pycromanager():
    with patch("autoopenraman.gui.Core") as mock_core, patch(
        "autoopenraman.gui.Studio"
    ) as mock_studio, patch("autoopenraman.gui.Acquisition") as mock_acquisition:
        # Set up mock Core for image acquisition
        mock_core_instance = MagicMock()
        mock_core_instance.snap_image.return_value = None
        mock_core_instance.get_tagged_image.return_value = MagicMock(
            pix=[0] * 100, tags={"Width": 10, "Height": 10}
        )
        mock_core_instance.get_shutter_open.return_value = False

        # Return the mock instance when Core() is called
        mock_core.return_value = mock_core_instance

        # Set up mock Studio
        mock_studio.return_value = MagicMock()

        # Set up mock acquisition
        mock_acquisition.return_value.__enter__.return_value = MagicMock()

        yield


@pytest.fixture
def app():
    """Create a QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def gui_window(app):
    """Create a test instance of our GUI with debug mode enabled."""
    window = AutoOpenRamanGUI(debug=True)
    yield window
    window.close()


def test_gui_initialization(gui_window):
    """Test that the GUI initializes properly with both modes available."""
    # Check title and main components
    assert gui_window.windowTitle() == "AutoOpenRaman"

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


def test_live_mode_controls(gui_window):
    """Test that live mode controls are properly initialized."""
    # Check that live mode controls exist
    assert gui_window.reverse_x_check is not None
    assert gui_window.median_filter_check is not None
    assert gui_window.kernel_size_input is not None
    assert gui_window.start_live_btn is not None
    assert gui_window.stop_live_btn is not None

    # Check default state
    assert gui_window.reverse_x_check.isChecked() is False
    assert gui_window.median_filter_check.isChecked() is False
    assert gui_window.kernel_size_input.text() == "3"
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
    assert gui_window.exp_dir_input.text() == "data/"
    assert gui_window.n_averages_input.value() == 1
    assert gui_window.shutter_check.isChecked() is False
    assert gui_window.randomize_check.isChecked() is False
