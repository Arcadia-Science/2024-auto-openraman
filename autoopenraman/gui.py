import json
import sys
import time
from pathlib import Path

import numpy as np
from pycromanager import Acquisition, Core, Studio, multi_d_acquisition_events
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph import PlotWidget
from scipy.signal import medfilt

from autoopenraman import config_profile
from autoopenraman.utils import extract_stage_positions, image_to_spectrum, write_spectrum


# Worker Thread for Image Acquisition (used in Live Mode)
class CameraWorker(QThread):
    data_acquired = pyqtSignal(np.ndarray)  # Signal to emit spectrum data

    def __init__(self):
        super().__init__()
        self._core = Core()
        self.running = True

    def run(self):
        while self.running:
            try:
                # Acquire image
                self._core.snap_image()
                tagged_image = self._core.get_tagged_image()
                image_2d = np.reshape(
                    tagged_image.pix,
                    newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
                )
                spectrum = image_to_spectrum(image_2d)
                self.data_acquired.emit(spectrum)
            except Exception as e:
                print(f"Error snapping image: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# Main Application Class
class AutoOpenRamanGUI(QMainWindow):
    def __init__(self, debug=False):
        super().__init__()
        self.debug = debug

        # Pycro-Manager Studio Initialization
        self._studio = Studio(convert_camel_case=True)
        self._core = Core()

        # Main GUI Setup
        self.setWindowTitle("AutoOpenRaman")
        self.setGeometry(100, 100, 1000, 700)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create the mode selection buttons at the top
        self.create_mode_selector()

        # Create stacked widget to hold different mode UIs
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create Live Mode Page
        self.live_mode_widget = self.create_live_mode_page()
        self.stacked_widget.addWidget(self.live_mode_widget)

        # Create Acquisition Mode Page
        self.acq_mode_widget = self.create_acquisition_mode_page()
        self.stacked_widget.addWidget(self.acq_mode_widget)

        # Initialize variables for live mode
        self.worker = None
        self.apply_median_filter = False
        self.reverse_x = False

        # Initialize variables for acquisition mode
        self.xy_positions = None
        self.labels = None
        self.spectrum_list = []

        # Debug mode timer
        if self.debug:
            print("Debug mode enabled")
            QTimer.singleShot(5000, self.close)

    def create_mode_selector(self):
        """Create the mode selection buttons at the top of the window"""
        mode_layout = QHBoxLayout()

        self.live_mode_btn = QPushButton("Live Mode")
        self.live_mode_btn.setCheckable(True)
        self.live_mode_btn.setChecked(True)
        self.live_mode_btn.clicked.connect(lambda: self.switch_mode(0))

        self.acq_mode_btn = QPushButton("Acquisition Mode")
        self.acq_mode_btn.setCheckable(True)
        self.acq_mode_btn.clicked.connect(lambda: self.switch_mode(1))

        mode_layout.addWidget(self.live_mode_btn)
        mode_layout.addWidget(self.acq_mode_btn)

        self.main_layout.addLayout(mode_layout)

    def switch_mode(self, index):
        """Switch between different modes (Live or Acquisition)"""
        # Update button states
        if index == 0:
            self.live_mode_btn.setChecked(True)
            self.acq_mode_btn.setChecked(False)
        else:
            self.live_mode_btn.setChecked(False)
            self.acq_mode_btn.setChecked(True)

        # Stop any ongoing acquisition in live mode
        if self.worker and index == 1:
            self.stop_live_acquisition()

        # Switch the stacked widget
        self.stacked_widget.setCurrentIndex(index)

    def create_live_mode_page(self):
        """Create the Live Mode page"""
        live_widget = QWidget()
        live_layout = QVBoxLayout(live_widget)

        # Plot Widget
        self.live_plot_widget = PlotWidget()
        self.live_plot = self.live_plot_widget.plot()
        live_layout.addWidget(self.live_plot_widget)

        # Controls Group
        controls_group = QGroupBox("Live Mode Controls")
        controls_layout = QHBoxLayout(controls_group)

        # Reverse X Checkbox
        self.reverse_x_check = QCheckBox("Reverse X")
        self.reverse_x_check.stateChanged.connect(self.toggle_reverse_x)
        controls_layout.addWidget(self.reverse_x_check)

        # Median Filter Checkbox
        self.median_filter_check = QCheckBox("Apply Median Filter")
        self.median_filter_check.stateChanged.connect(self.toggle_median_filter)
        controls_layout.addWidget(self.median_filter_check)

        # Kernel Size Input
        controls_layout.addWidget(QLabel("Kernel Size:"))
        self.kernel_size_input = QLineEdit("3")
        controls_layout.addWidget(self.kernel_size_input)

        # Start/Stop Button
        self.start_live_btn = QPushButton("Start Live")
        self.start_live_btn.clicked.connect(self.start_live_acquisition)
        controls_layout.addWidget(self.start_live_btn)

        self.stop_live_btn = QPushButton("Stop Live")
        self.stop_live_btn.clicked.connect(self.stop_live_acquisition)
        self.stop_live_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_live_btn)

        live_layout.addWidget(controls_group)

        return live_widget

    def create_acquisition_mode_page(self):
        """Create the Acquisition Mode page"""
        acq_widget = QWidget()
        acq_layout = QVBoxLayout(acq_widget)

        # Plot Widget for Acquisition Mode
        self.acq_plot_widget = PlotWidget()
        self.acq_plot = self.acq_plot_widget.plot()
        acq_layout.addWidget(self.acq_plot_widget)

        # Settings Group
        settings_group = QGroupBox("Acquisition Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Position File Row
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position File:"))
        self.position_file_input = QLineEdit()
        self.position_file_input.setReadOnly(True)
        pos_layout.addWidget(self.position_file_input)

        self.browse_pos_btn = QPushButton("Browse...")
        self.browse_pos_btn.clicked.connect(self.browse_position_file)
        pos_layout.addWidget(self.browse_pos_btn)
        settings_layout.addLayout(pos_layout)

        # Experiment Directory Row
        exp_dir_layout = QHBoxLayout()
        exp_dir_layout.addWidget(QLabel("Experiment Directory:"))
        self.exp_dir_input = QLineEdit("data/")
        exp_dir_layout.addWidget(self.exp_dir_input)

        self.browse_dir_btn = QPushButton("Browse...")
        self.browse_dir_btn.clicked.connect(self.browse_experiment_dir)
        exp_dir_layout.addWidget(self.browse_dir_btn)
        settings_layout.addLayout(exp_dir_layout)

        # Number of Averages Row
        n_avg_layout = QHBoxLayout()
        n_avg_layout.addWidget(QLabel("Number of Averages:"))
        self.n_averages_input = QSpinBox()
        self.n_averages_input.setMinimum(1)
        self.n_averages_input.setMaximum(1000)
        self.n_averages_input.setValue(1)
        n_avg_layout.addWidget(self.n_averages_input)
        settings_layout.addLayout(n_avg_layout)

        # Checkboxes Row
        checkboxes_layout = QHBoxLayout()

        self.shutter_check = QCheckBox("Close Shutter Between Acquisitions")
        checkboxes_layout.addWidget(self.shutter_check)

        self.randomize_check = QCheckBox("Randomize Stage Positions")
        checkboxes_layout.addWidget(self.randomize_check)

        settings_layout.addLayout(checkboxes_layout)

        # Start Acquisition Button
        self.start_acq_btn = QPushButton("Start Acquisition")
        self.start_acq_btn.clicked.connect(self.start_acquisition)
        settings_layout.addWidget(self.start_acq_btn)

        acq_layout.addWidget(settings_group)

        return acq_widget

    # Live Mode Functions
    def toggle_median_filter(self):
        """Toggle median filter application."""
        self.apply_median_filter = self.median_filter_check.isChecked()

    def toggle_reverse_x(self):
        """Toggle X-axis reversal."""
        self.reverse_x = self.reverse_x_check.isChecked()

    def start_live_acquisition(self):
        """Start the worker thread for live acquisition."""
        print("Starting live acquisition...")
        self.worker = CameraWorker()
        self.worker.data_acquired.connect(self.update_live_plot)
        self.worker.start()

        self.start_live_btn.setEnabled(False)
        self.stop_live_btn.setEnabled(True)

    def stop_live_acquisition(self):
        """Stop the worker thread."""
        if self.worker:
            self.worker.stop()
        self.start_live_btn.setEnabled(True)
        self.stop_live_btn.setEnabled(False)
        print("Stopped live acquisition...")

    def update_live_plot(self, spectrum):
        """Update the live plot with new spectrum data."""
        if self.apply_median_filter:
            try:
                kernel_size = int(self.kernel_size_input.text())
                spectrum = medfilt(spectrum, kernel_size=kernel_size)
            except ValueError:
                print("Invalid kernel size. Using default of 3.")
                spectrum = medfilt(spectrum, kernel_size=3)

        if self.reverse_x:
            spectrum = spectrum[::-1]

        x_data = np.linspace(0, len(spectrum), len(spectrum))
        self.live_plot.setData(x_data, spectrum)

    # Acquisition Mode Functions
    def browse_position_file(self):
        """Open file dialog to select position file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Position File", "", "Position Files (*.pos *.json);;All Files (*)"
        )
        if file_path:
            self.position_file_input.setText(file_path)

    def browse_experiment_dir(self):
        """Open directory dialog to select experiment directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Experiment Directory", config_profile.save_dir
        )
        if dir_path:
            # Get relative path from save_dir if possible
            try:
                rel_path = Path(dir_path).relative_to(config_profile.save_dir)
                self.exp_dir_input.setText(str(rel_path))
            except ValueError:
                # If not relative to save_dir, use absolute path
                self.exp_dir_input.setText(dir_path)

    def start_acquisition(self):
        """Start the acquisition process"""
        position_file = self.position_file_input.text() if self.position_file_input.text() else None
        n_averages = self.n_averages_input.value()
        exp_dir = self.exp_dir_input.text()
        shutter = self.shutter_check.isChecked()
        randomize_stage_positions = self.randomize_check.isChecked()

        # Check if position file is valid when randomize is checked
        if randomize_stage_positions and not position_file:
            print("Error: Randomizing stage positions requires a position file.")
            return

        # Validate and create experiment directory
        exp_path = Path(config_profile.save_dir) / exp_dir

        if not exp_path.is_dir():
            print(f"Creating save directory: {exp_path}")
            exp_path.mkdir(parents=True)
        elif len(list(exp_path.glob("*.csv"))) > 0:
            # In a GUI, we should show a dialog here
            print(f"Warning: {exp_path} is not empty. Files may be overwritten.")

        # Disable controls during acquisition
        self.start_acq_btn.setEnabled(False)

        # Run acquisition in a separate thread
        self.acquisition_thread = QThread()
        self.acquisition_worker = AcquisitionWorker(
            n_averages, exp_path, position_file, shutter, randomize_stage_positions, self
        )
        self.acquisition_worker.moveToThread(self.acquisition_thread)
        self.acquisition_thread.started.connect(self.acquisition_worker.run_acquisition)
        self.acquisition_worker.finished.connect(self.acquisition_thread.quit)
        self.acquisition_worker.finished.connect(lambda: self.start_acq_btn.setEnabled(True))
        self.acquisition_worker.spectrum_ready.connect(self.update_acq_plot)
        self.acquisition_thread.start()

    def update_acq_plot(self, x, y, title):
        """Update the acquisition plot"""
        self.acq_plot.setData(x, y)
        self.acq_plot_widget.setTitle(title)

    def closeEvent(self, event):
        """Handle window close event to stop worker thread."""
        if self.worker:
            self.worker.stop()
        event.accept()


# Worker for Acquisition Mode
class AcquisitionWorker(QThread):
    finished = pyqtSignal()
    spectrum_ready = pyqtSignal(object, object, str)  # x, y, title

    def __init__(
        self, n_averages, exp_path, position_file, shutter, randomize_stage_positions, parent=None
    ):
        super().__init__(parent)
        self.n_averages = n_averages
        self.exp_path = Path(exp_path)
        self.position_file = position_file
        self.shutter = shutter
        self.randomize_stage_positions = randomize_stage_positions

        self.spectrum_list = []

        if position_file is not None:
            self.xy_positions, self.labels = extract_stage_positions(
                position_file, randomize_stage_positions
            )
        else:
            self.xy_positions = None
            self.labels = None

        if self.shutter:
            self.core = Core()
            shutter_name = config_profile.shutter_name

            try:
                self.core.set_shutter_device(shutter_name)
            except ValueError as e:
                raise ValueError(f"Shutter device {shutter_name} not found in Micro-Manager") from e

            self.core.set_auto_shutter(False)

            # close shutter
            self._set_shutter_open_safe(is_open=False)

    def _set_shutter_open_safe(self, is_open: bool) -> None:
        """Set the shutter open safely."""
        # if the shutter is already in the desired state, do nothing
        if self.core.get_shutter_open() == is_open:
            print(f"Shutter is already {'open' if is_open else 'closed'}")
            return

        # if the shutter is not in the desired state, try to set it
        self.core.set_shutter_open(is_open)

        # if the shutter is still not in the desired state, raise an error
        if self.core.get_shutter_open() != is_open:
            raise ValueError(f"Shutter could not be set to {'open' if is_open else 'closed'}")

        print(f"Shutter {'opened' if is_open else 'closed'}")

    def _save_metadata(self, _filename: str, _metadata: dict) -> None:
        """Save the metadata to a JSON file."""
        # add the acquisition parameters to the metadata
        _metadata["Number of averages"] = self.n_averages
        _metadata["Stage position file"] = self.position_file
        _metadata["DateTime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        with open(self.exp_path / (_filename + ".json"), "w") as f:
            json.dump(_metadata, f)

    def process_image(self, image: np.ndarray, metadata: dict) -> None:
        """Process the acquired image."""
        fname = metadata.get("PositionName", metadata.get("Position", "DefaultPos"))
        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        # Calculate running average
        running_avg = (
            np.mean(self.spectrum_list, axis=0) if len(self.spectrum_list) > 0 else img_spectrum
        )

        # Emit signal to update plot in main thread
        title = f"Position: {fname} - Average {len(self.spectrum_list)}/{self.n_averages}"
        self.spectrum_ready.emit(x, running_avg, title)

        # if this is the final spectrum in the average, save average spectrum and metadata
        if len(self.spectrum_list) == self.n_averages:
            write_spectrum(self.exp_path / (fname + ".csv"), x, running_avg)
            self._save_metadata(fname, metadata)
            self.spectrum_list = []

    def run_acquisition(self) -> None:
        """Run the acquisition."""
        start = time.time()

        with Acquisition(show_display=False) as acq:
            events = multi_d_acquisition_events(
                num_time_points=self.n_averages,
                time_interval_s=0,
                xy_positions=self.xy_positions,
                position_labels=self.labels,
                order="pt",
            )

            for _, event in enumerate(events):
                future = acq.acquire(event)

                if self.shutter and (event["axes"]["time"] == 0):
                    # open shutter before first image in timeseries
                    self._set_shutter_open_safe(is_open=True)

                image, metadata = future.await_image_saved(
                    event["axes"], return_image=True, return_metadata=True
                )
                self.process_image(image, metadata)

                if self.shutter and (event["axes"]["time"] == self.n_averages - 1):
                    # close shutter after last image in timeseries
                    self._set_shutter_open_safe(is_open=False)

        print(f"Time elapsed: {time.time() - start:.2f} s")
        self.finished.emit()


def main():
    app = QApplication(sys.argv)
    window = AutoOpenRamanGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
