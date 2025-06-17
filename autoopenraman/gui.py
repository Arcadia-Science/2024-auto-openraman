import json
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
from pycromanager import Acquisition, Core, Studio, multi_d_acquisition_events
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph import PlotWidget
from scipy.signal import medfilt

from autoopenraman import config_profile
from autoopenraman.calibration import DEFAULT_EXCITATION_WAVELENGTH_NM, RamanCalibrator
from autoopenraman.utils import (
    extract_stage_positions,
    image_to_spectrum,
    write_spectrum,
)


# Worker Thread for Image Acquisition (used in Live Mode)
class CameraWorker(QThread):
    data_acquired = pyqtSignal(np.ndarray)  # Signal to emit spectrum data

    def __init__(self):
        super().__init__()
        self._core = Core()
        self.running = True
        self.pause_acquisition = False
        self.last_spectrum = None  # Store the last acquired spectrum

    def run(self):
        while self.running:
            # Check if acquisition is paused (for background capture)
            if self.pause_acquisition:
                # Sleep briefly to avoid CPU overuse
                self.msleep(50)
                continue

            try:
                # Acquire image
                self._core.snap_image()  # type: ignore
                tagged_image = self._core.get_tagged_image()  # type: ignore
                image_2d = np.reshape(
                    tagged_image.pix,
                    newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
                )
                spectrum = image_to_spectrum(image_2d)

                # Convert to float64 to allow for negative values after background subtraction
                spectrum = spectrum.astype(np.float64)

                # Store the spectrum for potential background capture
                self.last_spectrum = spectrum.copy()

                # Emit the spectrum to be displayed
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

        # Initialize variables for live mode
        self.worker = None
        self.apply_median_filter = False
        self.reverse_x = False
        self.background_spectrum = None  # For background subtraction
        self.background_active = False  # Flag for background subtraction

        # Initialize variables for acquisition mode
        self.xy_positions = None
        self.labels = None
        self.spectrum_list = []

        # Initialize calibration variables
        self.calibrator = RamanCalibrator()
        self.calibration_active = False
        self.x_axis_mode = "pixels"  # Can be "pixels" or "wavenumbers"

        # Create the mode selection buttons at the top
        self.create_mode_selector()

        # Create the shared plot widget
        self.create_shared_plot()

        # Create the common controls (filtering, etc.)
        self.create_common_controls()

        # Create stacked widget to hold mode-specific UIs
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create Live Mode Page
        self.live_mode_widget = self.create_live_mode_page()
        self.stacked_widget.addWidget(self.live_mode_widget)

        # Create Acquisition Mode Page
        self.acq_mode_widget = self.create_acquisition_mode_page()
        self.stacked_widget.addWidget(self.acq_mode_widget)

        # Debug mode timer
        if self.debug:
            print("Debug mode enabled")
            QTimer.singleShot(5000, self.close)  # type: ignore

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

    def create_shared_plot(self):
        """Create a single plot widget that will be shared between modes"""
        # Create a container for the plot
        plot_container = QGroupBox("Spectrum Display")
        plot_layout = QVBoxLayout(plot_container)

        # Create the plot widget
        self.plot_widget = PlotWidget()
        self.plot_widget.setLabel("left", "Intensity")
        self.plot_widget.setLabel("bottom", "Pixels")

        # Initialize the main plot line (colors will be set in reset_plot_area)
        self.plot = self.plot_widget.plot()

        plot_layout.addWidget(self.plot_widget)

        # Add the plot container to the main layout
        self.main_layout.addWidget(plot_container)

        # Set initial plot state for live mode (default)
        self.reset_plot_area("live")

    def create_common_controls(self):
        """Create controls that are common to both live and acquisition modes"""
        common_controls = QGroupBox("Spectrum Processing")

        # Use a vertical layout to stack control rows
        main_controls_layout = QVBoxLayout(common_controls)

        # First row of controls
        processing_controls = QHBoxLayout()

        # Reverse X Checkbox
        self.reverse_x_check = QCheckBox("Reverse X")
        self.reverse_x_check.stateChanged.connect(self.toggle_reverse_x)
        processing_controls.addWidget(self.reverse_x_check)

        # Median Filter Checkbox
        self.median_filter_check = QCheckBox("Apply Median Filter")
        self.median_filter_check.stateChanged.connect(self.toggle_median_filter)
        processing_controls.addWidget(self.median_filter_check)

        # Kernel Size Input
        processing_controls.addWidget(QLabel("Kernel Size:"))
        self.kernel_size_input = QLineEdit("3")
        processing_controls.addWidget(self.kernel_size_input)

        # Show Current Measurement Checkbox (for acquisition mode)
        self.show_current_check = QCheckBox("Show Current Measurement")
        self.show_current_check.setChecked(True)
        self.show_current_check.stateChanged.connect(self.toggle_show_current)
        processing_controls.addWidget(self.show_current_check)

        # Add the first row to the main layout
        main_controls_layout.addLayout(processing_controls)

        # Second row - Calibration controls
        calibration_controls = QHBoxLayout()

        # X-axis mode selector
        calibration_controls.addWidget(QLabel("X-Axis:"))
        self.x_axis_mode_combo = QComboBox()
        self.x_axis_mode_combo.addItems(["Pixels", "Wavenumbers (cm⁻¹)"])
        self.x_axis_mode_combo.currentIndexChanged.connect(self.change_x_axis_mode)
        calibration_controls.addWidget(self.x_axis_mode_combo)

        # Calibrate button
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.clicked.connect(self.open_calibration_dialog)
        calibration_controls.addWidget(self.calibrate_btn)

        # Load calibration button
        self.load_calibration_btn = QPushButton("Load Calibration")
        self.load_calibration_btn.clicked.connect(self.load_calibration)
        calibration_controls.addWidget(self.load_calibration_btn)

        # Save calibration button
        self.save_calibration_btn = QPushButton("Save Calibration")
        self.save_calibration_btn.clicked.connect(self.save_calibration)
        self.save_calibration_btn.setEnabled(False)  # Disabled until calibration is performed
        calibration_controls.addWidget(self.save_calibration_btn)

        # Add second row to main layout
        main_controls_layout.addLayout(calibration_controls)

        # Add the common controls to the main layout
        self.main_layout.addWidget(common_controls)

    def reset_plot_area(self, mode):
        """Reset the plot area when switching modes"""
        # Clear any existing plots
        self.plot_widget.clear()

        # Create the main plot with appropriate color for the mode
        if mode == "live":
            # Set color based on background subtraction state
            if self.background_active:
                plot_color = "g"  # Green for background-subtracted
                plot_title = "Live Mode - Background Subtracted"
            else:
                plot_color = "b"  # Blue for normal display
                plot_title = "Live Mode - Spectrum"

            self.plot = self.plot_widget.plot(pen=plot_color)
            self.plot_widget.setTitle(plot_title)

            # Hide current spectrum plot if it exists
            if hasattr(self, "current_spectrum_plot"):
                self.current_spectrum_plot = None

        elif mode == "acquisition":
            # Blue plot for the running average
            self.plot = self.plot_widget.plot(pen="b")

            # Red plot for current measurement (if enabled)
            self.current_spectrum_plot = self.plot_widget.plot(pen="r")
            self.current_spectrum_plot.setVisible(self.show_current_check.isChecked())

            self.plot_widget.setTitle("Acquisition Mode - Ready")

    def switch_mode(self, index):
        """Switch between different modes (Live or Acquisition)"""
        # Update button states
        if index == 0:
            # Switching to Live mode
            self.live_mode_btn.setChecked(True)
            self.acq_mode_btn.setChecked(False)
            self.reset_plot_area("live")
        else:
            # Switching to Acquisition mode
            self.live_mode_btn.setChecked(False)
            self.acq_mode_btn.setChecked(True)
            self.reset_plot_area("acquisition")

        # Stop any ongoing acquisition in live mode
        if self.worker and index == 1:
            self.stop_live_acquisition()

        # Switch the stacked widget
        self.stacked_widget.setCurrentIndex(index)

    def create_live_mode_page(self):
        """Create the Live Mode page"""
        live_widget = QWidget()
        live_layout = QVBoxLayout(live_widget)

        # Controls Group
        controls_group = QGroupBox("Live Mode Controls")
        controls_layout = QVBoxLayout(controls_group)

        # First row - Start/Stop buttons
        acquisition_layout = QHBoxLayout()

        # Start/Stop Button
        self.start_live_btn = QPushButton("Start Live")
        self.start_live_btn.clicked.connect(self.start_live_acquisition)
        acquisition_layout.addWidget(self.start_live_btn)

        self.stop_live_btn = QPushButton("Stop Live")
        self.stop_live_btn.clicked.connect(self.stop_live_acquisition)
        self.stop_live_btn.setEnabled(False)
        acquisition_layout.addWidget(self.stop_live_btn)

        controls_layout.addLayout(acquisition_layout)

        # Second row - Background subtraction buttons
        background_layout = QHBoxLayout()

        # Store Background Button
        self.store_bg_btn = QPushButton("Store Background")
        self.store_bg_btn.clicked.connect(self.store_background)
        self.store_bg_btn.setToolTip("Store current spectrum as background for subtraction")
        background_layout.addWidget(self.store_bg_btn)

        # Clear Background Button
        self.clear_bg_btn = QPushButton("Clear Background")
        self.clear_bg_btn.clicked.connect(self.clear_background)
        self.clear_bg_btn.setToolTip("Clear stored background and disable subtraction")
        self.clear_bg_btn.setEnabled(False)  # Disabled until background is stored
        background_layout.addWidget(self.clear_bg_btn)

        # Background status indicator
        self.bg_status_label = QLabel("Background: Not set")
        background_layout.addWidget(self.bg_status_label)

        controls_layout.addLayout(background_layout)

        live_layout.addWidget(controls_group)

        return live_widget

    def create_acquisition_mode_page(self):
        """Create the Acquisition Mode page"""
        acq_widget = QWidget()
        acq_layout = QVBoxLayout(acq_widget)

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
        self.exp_dir_input = QLineEdit("")
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

        # Timelapse Settings
        timelapse_layout = QHBoxLayout()

        # Number of Time Points
        timelapse_layout.addWidget(QLabel("Time Points:"))
        self.num_time_points_input = QSpinBox()
        self.num_time_points_input.setMinimum(1)
        self.num_time_points_input.setMaximum(1000)
        self.num_time_points_input.setValue(1)
        timelapse_layout.addWidget(self.num_time_points_input)

        # Time Interval
        timelapse_layout.addWidget(QLabel("Interval (s):"))
        self.time_interval_input = QSpinBox()
        self.time_interval_input.setMinimum(0)
        self.time_interval_input.setMaximum(3600)
        self.time_interval_input.setValue(0)
        timelapse_layout.addWidget(self.time_interval_input)

        settings_layout.addLayout(timelapse_layout)

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

    def toggle_show_current(self):
        """Toggle visibility of current measurement in acquisition mode."""
        show_current = self.show_current_check.isChecked()
        if hasattr(self, "current_spectrum_plot"):
            if self.current_spectrum_plot is not None:
                self.current_spectrum_plot.setVisible(show_current)

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

    def store_background(self):
        """Store the current spectrum as background for subtraction."""
        if self.worker and self.worker.isRunning():
            # Get the most recent spectrum
            self.worker.pause_acquisition = True
            # Wait a moment to ensure we're not in the middle of acquisition
            QTimer.singleShot(100, self._do_store_background)
        else:
            # Not in live mode - warn user
            QMessageBox.warning(
                self,
                "Background Storage",
                "Please start Live Mode first to capture a background spectrum.",
            )

    def _do_store_background(self):
        """Internal method to actually store the background after pausing acquisition."""
        if (
            self.worker is None
            or not hasattr(self.worker, "last_spectrum")
            or self.worker.last_spectrum is None
        ):
            QMessageBox.warning(
                self,
                "Background Storage",
                "No spectrum available. Please wait for at least one spectrum to be acquired.",
            )
            if self.worker and self.worker.isRunning():
                self.worker.pause_acquisition = False
            return

        # Store the background spectrum (raw, unprocessed)
        self.background_spectrum = self.worker.last_spectrum.copy()
        self.background_active = True

        # Update UI
        self.bg_status_label.setText("Background: Active")
        self.clear_bg_btn.setEnabled(True)
        self.worker.pause_acquisition = False

        # Update the plot color to indicate background subtraction
        self.plot.setPen("g")  # Green for background-subtracted spectra

        print("Background spectrum stored and subtraction enabled")

    def clear_background(self):
        """Clear the stored background and disable subtraction."""
        self.background_spectrum = None
        self.background_active = False

        # Update UI
        self.bg_status_label.setText("Background: Not set")
        self.clear_bg_btn.setEnabled(False)

        # Restore plot color
        self.plot.setPen("b")  # Blue for regular spectra

        print("Background cleared and subtraction disabled")

    def update_live_plot(self, spectrum):
        """Update the live plot with new spectrum data."""
        # Apply background subtraction if active
        if self.background_active and self.background_spectrum is not None:
            # Handle different lengths if they occur
            if len(spectrum) == len(self.background_spectrum):
                # Subtract background - allow negative values
                subtracted_spectrum = spectrum - self.background_spectrum
                # Process the subtracted spectrum
                processed_spectrum = self.process_spectrum(subtracted_spectrum)
                # Set title to indicate background subtraction
                plot_title = "Live Mode - Background Subtracted"
                # Use green color for background-subtracted data
                plot_color = "g"
            else:
                # Sizes don't match - can't subtract
                processed_spectrum = self.process_spectrum(spectrum)
                plot_title = "Live Mode - Background Size Mismatch!"
                plot_color = "r"  # Red to indicate an error
        else:
            # Normal processing without background subtraction
            processed_spectrum = self.process_spectrum(spectrum)
            plot_title = "Live Mode - Spectrum"
            plot_color = "b"  # Blue for regular data

        # Create the x_data array
        if self.x_axis_mode == "wavenumbers" and self.calibration_active:
            # Use calibrated wavenumbers for the x-axis
            x_data = self.calibrator.apply_calibration(np.arange(len(processed_spectrum)))
            # Update x-axis label
            self.plot_widget.setLabel("bottom", "Wavenumber (cm⁻¹)")
        else:
            # Use pixel indices for the x-axis
            x_data = np.arange(len(processed_spectrum))
            # Update x-axis label
            self.plot_widget.setLabel("bottom", "Pixels")

        # Set pen color based on whether background subtraction is active
        self.plot.setPen(plot_color)

        # Update the plot with processed data
        self.plot.setData(x_data, processed_spectrum)

        # Update title
        self.plot_widget.setTitle(plot_title)

    def process_spectrum(self, spectrum):
        """Apply common processing to spectrum data based on filter settings."""
        processed_spectrum = spectrum.copy()

        # Apply median filter if enabled
        if self.apply_median_filter:
            try:
                kernel_size = int(self.kernel_size_input.text())
                processed_spectrum = medfilt(processed_spectrum, kernel_size=kernel_size)
            except ValueError:
                print("Invalid kernel size. Using default of 3.")
                processed_spectrum = medfilt(processed_spectrum, kernel_size=3)

        # Reverse X if enabled
        if self.reverse_x:
            processed_spectrum = processed_spectrum[::-1]

        return processed_spectrum

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
            self, "Select Experiment Directory", str(config_profile.save_dir)
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
        num_time_points = self.num_time_points_input.value()
        time_interval_s = self.time_interval_input.value()

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

        # Get current filter settings
        try:
            kernel_size = int(self.kernel_size_input.text())
        except ValueError:
            kernel_size = 3
            print("Invalid kernel size. Using default of 3.")

        # Run acquisition in a separate thread
        self.acquisition_thread = QThread()
        self.acquisition_worker = AcquisitionWorker(
            n_averages,
            exp_path,
            position_file,
            shutter,
            randomize_stage_positions,
            self.apply_median_filter,
            kernel_size,
            self.reverse_x,
            self,
            num_time_points,
            time_interval_s,
        )
        self.acquisition_worker.moveToThread(self.acquisition_thread)
        self.acquisition_thread.started.connect(self.acquisition_worker.run_acquisition)
        self.acquisition_worker.finished.connect(self.acquisition_thread.quit)
        self.acquisition_worker.finished.connect(lambda: self.start_acq_btn.setEnabled(True))
        self.acquisition_worker.spectrum_ready.connect(self.update_acq_plot)
        self.acquisition_thread.start()

    def update_acq_plot(self, x, current_spectrum, running_avg, title):
        """Update the acquisition plot showing both current spectrum and running average"""
        # Process spectra
        processed_current = self.process_spectrum(current_spectrum)
        processed_avg = self.process_spectrum(running_avg)

        # Create x values based on the current mode
        if self.x_axis_mode == "wavenumbers" and self.calibration_active:
            # Use calibrated wavenumbers for the x-axis
            x_values = self.calibrator.apply_calibration(np.arange(len(processed_avg)))
            # Update x-axis label
            self.plot_widget.setLabel("bottom", "Wavenumber (cm⁻¹)")
        else:
            # Use pixel indices for the x-axis
            x_values = np.arange(len(processed_avg))
            # Update x-axis label
            self.plot_widget.setLabel("bottom", "Pixels")

        # Update running average plot (blue)
        self.plot.setData(x_values, processed_avg)

        # Check if we need to recreate the current spectrum plot
        if self.show_current_check.isChecked():
            # Create the current spectrum plot if it doesn't exist or was reset
            if not hasattr(self, "current_spectrum_plot") or self.current_spectrum_plot is None:
                self.current_spectrum_plot = self.plot_widget.plot(pen="r")

            # Update the current spectrum data
            self.current_spectrum_plot.setData(x_values, processed_current)
            self.current_spectrum_plot.setVisible(True)

            # Title with both plots indicated
            full_title = f"{title} (Blue=Running Average, Red=Current Measurement)"
        else:
            # If we have a current spectrum plot but it's disabled, hide it
            if hasattr(self, "current_spectrum_plot") and self.current_spectrum_plot is not None:
                self.current_spectrum_plot.setVisible(False)

            # Title with only average indicated
            full_title = f"{title} (Running Average)"

        # Update the plot title
        self.plot_widget.setTitle(full_title)

        # Make sure the GUI refreshes to show the new data immediately
        QApplication.processEvents()

    def change_x_axis_mode(self, index):
        """Change the x-axis mode (pixels or wavenumbers)."""
        if index == 0:
            self.x_axis_mode = "pixels"
        else:
            self.x_axis_mode = "wavenumbers"
            if not self.calibration_active:
                QMessageBox.warning(
                    self,
                    "Calibration Required",
                    (
                        "Wavenumber display requires calibration. "
                        "Please calibrate or load a calibration file."
                    ),
                )

        # Update the current plot
        if self.worker and self.worker.isRunning():
            # Live mode is running, it will update on next frame
            pass
        elif hasattr(self, "spectrum_list") and len(self.spectrum_list) > 0:
            # Manually update the acquisition plot with the most recent data
            self.update_acq_plot(
                None,  # x values will be generated in update_acq_plot
                self.spectrum_list[-1],
                np.mean(self.spectrum_list, axis=0),
                "Current Spectrum",
            )

    def open_calibration_dialog(self):
        """Open the calibration dialog to perform calibration."""
        dialog = CalibrationDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Get the neon and acetonitrile spectra from the dialog
            neon_spectrum = dialog.neon_spectrum
            acetonitrile_spectrum = dialog.acetonitrile_spectrum

            if neon_spectrum is None or acetonitrile_spectrum is None:
                QMessageBox.warning(
                    self,
                    "Calibration Error",
                    "Both neon and acetonitrile spectra are required for calibration.",
                )
                return

            try:
                # Perform calibration
                self.calibrator.calibrate(neon_spectrum, acetonitrile_spectrum)
                self.calibration_active = True

                # Enable the save calibration button
                self.save_calibration_btn.setEnabled(True)

                # Update the plot if in wavenumber mode
                if self.x_axis_mode == "wavenumbers":
                    if self.worker and self.worker.isRunning():
                        # Live mode will update on next frame
                        pass
                    elif hasattr(self, "spectrum_list") and len(self.spectrum_list) > 0:
                        # Update the acquisition plot
                        self.update_acq_plot(
                            None,  # x values will be generated in update_acq_plot
                            self.spectrum_list[-1],
                            np.mean(self.spectrum_list, axis=0),
                            "Current Spectrum",
                        )

                QMessageBox.information(
                    self,
                    "Calibration Successful",
                    (
                        "Calibration completed successfully."
                        "X-axis can now be displayed in wavenumbers."
                    ),
                )

            except Exception as e:
                QMessageBox.warning(
                    self, "Calibration Error", f"Error during calibration: {str(e)}"
                )

    def load_calibration(self):
        """Load a calibration file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration File", "", "Calibration Files (*.cal);;All Files (*)"
        )

        if not file_path:
            return
        else:
            self.calibrator.load_calibration(Path(file_path))
            self.calibration_active = True
            self.save_calibration_btn.setEnabled(True)

            # Update the plot if in wavenumber mode
            if self.x_axis_mode == "wavenumbers":
                if self.worker and self.worker.isRunning():
                    # Live mode will update on next frame
                    pass
                elif hasattr(self, "spectrum_list") and len(self.spectrum_list) > 0:
                    # Update the acquisition plot
                    self.update_acq_plot(
                        None,  # x values will be generated in update_acq_plot
                        self.spectrum_list[-1],
                        np.mean(self.spectrum_list, axis=0),
                        "Current Spectrum",
                    )

            QMessageBox.information(
                self, "Calibration Loaded", "Calibration file loaded successfully."
            )

    def save_calibration(self):
        """Save the current calibration to a file."""
        if not self.calibration_active:
            QMessageBox.warning(
                self,
                "Save Calibration Error",
                "No calibration to save. Please perform calibration first.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration File", "", "Calibration Files (*.cal);;All Files (*)"
        )

        if file_path:
            try:
                if not file_path.endswith(".cal"):
                    file_path += ".cal"
                self.calibrator.save_calibration(Path(file_path))

                QMessageBox.information(
                    self, "Calibration Saved", "Calibration saved successfully."
                )

            except Exception as e:
                QMessageBox.warning(
                    self, "Save Calibration Error", f"Error saving calibration file: {str(e)}"
                )

    def closeEvent(self, event):
        """Handle window close event to stop worker thread."""
        if self.worker:
            self.worker.stop()
        event.accept()


class CalibrationDialog(QDialog):
    """Dialog for calibration using neon and acetonitrile spectra."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrum Calibration")
        self.setMinimumWidth(600)

        # Spectral data
        self.neon_spectrum = None
        self.acetonitrile_spectrum = None

        # Create the layout
        layout = QVBoxLayout(self)

        # Add information text
        info_label = QLabel(
            "Calibration requires two reference spectra:\n"
            "1. Neon lamp spectrum for rough wavelength calibration\n"
            "2. Acetonitrile spectrum for fine wavenumber calibration\n\n"
            "Please select the CSV files containing these spectra."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Neon spectrum file selection
        neon_layout = QHBoxLayout()
        neon_layout.addWidget(QLabel("Neon Spectrum File:"))
        self.neon_file_input = QLineEdit()
        self.neon_file_input.setReadOnly(True)
        neon_layout.addWidget(self.neon_file_input)
        self.browse_neon_btn = QPushButton("Browse...")
        self.browse_neon_btn.clicked.connect(self.browse_neon_file)
        neon_layout.addWidget(self.browse_neon_btn)
        layout.addLayout(neon_layout)

        # Acetonitrile spectrum file selection
        acn_layout = QHBoxLayout()
        acn_layout.addWidget(QLabel("Acetonitrile Spectrum File:"))
        self.acn_file_input = QLineEdit()
        self.acn_file_input.setReadOnly(True)
        acn_layout.addWidget(self.acn_file_input)
        self.browse_acn_btn = QPushButton("Browse...")
        self.browse_acn_btn.clicked.connect(self.browse_acn_file)
        acn_layout.addWidget(self.browse_acn_btn)
        layout.addLayout(acn_layout)

        # Excitation wavelength input
        excitation_layout = QHBoxLayout()
        excitation_layout.addWidget(QLabel("Excitation Wavelength (nm):"))
        self.excitation_input = QLineEdit(str(DEFAULT_EXCITATION_WAVELENGTH_NM))
        excitation_layout.addWidget(self.excitation_input)
        layout.addLayout(excitation_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.clicked.connect(self.accept)
        self.calibrate_btn.setEnabled(False)  # Disabled until both files are selected
        button_layout.addWidget(self.calibrate_btn)

        layout.addLayout(button_layout)

    def browse_neon_file(self):
        """Open file dialog to select neon spectrum file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Neon Spectrum File", "", "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.neon_file_input.setText(file_path)
            try:
                # Load the spectrum data
                spectrum_data = np.loadtxt(file_path, delimiter=",", skiprows=1)
                self.neon_spectrum = spectrum_data[:, 1]  # Take the intensity column

                # Enable the calibrate button if both files are selected
                if self.acetonitrile_spectrum is not None:
                    self.calibrate_btn.setEnabled(True)

            except Exception as e:
                QMessageBox.warning(
                    self, "File Error", f"Error loading neon spectrum file: {str(e)}"
                )
                self.neon_file_input.setText("")
                self.neon_spectrum = None
                self.calibrate_btn.setEnabled(False)

    def browse_acn_file(self):
        """Open file dialog to select acetonitrile spectrum file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Acetonitrile Spectrum File", "", "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.acn_file_input.setText(file_path)
            try:
                # Load the spectrum data
                spectrum_data = np.loadtxt(file_path, delimiter=",", skiprows=1)
                self.acetonitrile_spectrum = spectrum_data[:, 1]  # Take the intensity column

                # Enable the calibrate button if both files are selected
                if self.neon_spectrum is not None:
                    self.calibrate_btn.setEnabled(True)

            except Exception as e:
                QMessageBox.warning(
                    self, "File Error", f"Error loading acetonitrile spectrum file: {str(e)}"
                )
                self.acn_file_input.setText("")
                self.acetonitrile_spectrum = None
                self.calibrate_btn.setEnabled(False)

    def accept(self):
        """Override accept() to validate and collect all data."""
        if self.neon_spectrum is None or self.acetonitrile_spectrum is None:
            QMessageBox.warning(
                self,
                "Missing Data",
                "Both neon and acetonitrile spectra are required for calibration.",
            )
            return

        # Get the excitation wavelength
        try:
            excitation_wavelength = float(self.excitation_input.text())
            if excitation_wavelength <= 0:
                raise ValueError("Excitation wavelength must be positive")
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter a valid positive number for excitation wavelength.",
            )
            return

        # Set the excitation wavelength in the parent's calibrator
        if self.parent() is not None:
            self.parent().calibrator.excitation_wavelength_nm = excitation_wavelength  # type: ignore

        # Continue with accept
        super().accept()


# Worker for Acquisition Mode
class AcquisitionWorker(QThread):
    finished = pyqtSignal()
    spectrum_ready = pyqtSignal(object, object, object, str)
    # x, current_spectrum, running_avg, title

    def __init__(
        self,
        n_averages,
        exp_path,
        position_file,
        shutter,
        randomize_stage_positions,
        apply_median_filter=False,
        kernel_size=3,
        reverse_x=False,
        parent=None,
        num_time_points=1,
        time_interval_s=0,
    ):
        super().__init__(parent)
        self.n_averages = n_averages
        self.exp_path = Path(exp_path)
        self.position_file = position_file
        self.shutter = shutter
        self.randomize_stage_positions = randomize_stage_positions
        self.apply_median_filter = apply_median_filter
        self.kernel_size = kernel_size
        self.reverse_x = reverse_x
        self.num_time_points = num_time_points
        self.time_interval_s = time_interval_s

        # Get the parent window (GUI) to access calibration information
        self.parent_window = parent

        # List to store spectra for the current position
        self.spectrum_list = []

        # Flag to control whether to show latest individual spectrum alongside the average
        self.show_latest = True

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
                self.core.set_shutter_device(shutter_name)  # type: ignore
            except ValueError as e:
                raise ValueError(f"Shutter device {shutter_name} not found in Micro-Manager") from e

            self.core.set_auto_shutter(False)  # type: ignore

            # close shutter
            self._set_shutter_open_safe(is_open=False)

    def _set_shutter_open_safe(self, is_open: bool) -> None:
        """Set the shutter open safely."""
        # if the shutter is already in the desired state, do nothing
        if self.core.get_shutter_open() == is_open:  # type: ignore
            print(f"Shutter is already {'open' if is_open else 'closed'}")
            return

        # if the shutter is not in the desired state, try to set it
        self.core.set_shutter_open(is_open)  # type: ignore

        # if the shutter is still not in the desired state, raise an error
        if self.core.get_shutter_open() != is_open:  # type: ignore
            raise ValueError(f"Shutter could not be set to {'open' if is_open else 'closed'}")

        print(f"Shutter {'opened' if is_open else 'closed'}")

    def _save_metadata(self, _filename: str, _metadata: dict) -> None:
        """Save the metadata to a JSON file."""
        # add the acquisition parameters to the metadata
        _metadata["Number of averages"] = self.n_averages
        _metadata["Stage position file"] = self.position_file
        _metadata["DateTime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        _metadata["Timelapse"] = {
            "NumTimePoints": self.num_time_points,
            "TimeIntervalSeconds": self.time_interval_s,
        }

        # Add processing parameters
        _metadata["Processing"] = {
            "MedianFilter": {"Applied": self.apply_median_filter, "KernelSize": self.kernel_size},
            "ReverseX": self.reverse_x,
        }

        # Add calibration information if not already present
        if "Calibration" not in _metadata:
            if (
                self.parent_window is not None
                and hasattr(self.parent_window, "calibration_active")
                and self.parent_window.calibration_active
            ):
                _metadata["Calibration"] = {
                    "Applied": True,
                    "ExcitationWavelength": self.parent_window.calibrator.excitation_wavelength_nm,
                }
            else:
                _metadata["Calibration"] = {"Applied": False}

        with open(self.exp_path / (_filename + ".json"), "w") as f:
            json.dump(_metadata, f)

    def process_image(self, image: np.ndarray, metadata: dict) -> None:
        """Process the acquired image."""
        position_name = metadata.get("PositionName", metadata.get("Position", "DefaultPos"))
        axes = metadata.get("Axes")
        time_value = axes.get("time") if axes else "0"
        fname = f"{position_name}_{time_value}"

        img_spectrum = image_to_spectrum(image)

        # Create x-axis values as pixel indices
        x = np.arange(len(img_spectrum))

        # Add the new spectrum to our list
        self.spectrum_list.append(img_spectrum)
        current_count = len(self.spectrum_list)

        # Calculate running average
        running_avg = np.mean(self.spectrum_list, axis=0)

        # Create a more detailed title showing acquisition progress
        title = f"Position: {fname} - Spectrum {current_count}/{self.n_averages}"

        # Emit both the current spectrum and the running average
        # This allows the GUI to show both if desired
        self.spectrum_ready.emit(x, img_spectrum, running_avg, title)

        # If this was the final spectrum in the average, save data and reset for next position
        if current_count == self.n_averages:
            # Check if calibration is active and parent exists
            if (
                self.parent_window is not None
                and hasattr(self.parent_window, "calibration_active")
                and self.parent_window.calibration_active
            ):
                # Apply calibration to get wavenumbers
                wavenumbers = self.parent_window.calibrator.apply_calibration(x)

                # Save with calibrated wavenumbers (3-column format)
                write_spectrum(
                    self.exp_path / (fname + ".csv"),
                    x.tolist(),  # Pixel indices
                    running_avg,  # Intensity values
                    wavenumbers=wavenumbers,  # Calibrated wavenumbers
                )

                # Add calibration info to metadata
                metadata["Calibration"] = {
                    "Applied": True,
                    "ExcitationWavelength": self.parent_window.calibrator.excitation_wavelength_nm,
                }
            else:
                # Save without calibration (2-column format)
                write_spectrum(
                    self.exp_path / (fname + ".csv"),
                    x.tolist(),  # Pixel indices
                    running_avg,  # Intensity values
                )

                # Note that calibration was not applied
                metadata["Calibration"] = {"Applied": False}

            # Save metadata
            self._save_metadata(fname, metadata)

            # Clear the spectrum list for the next position
            self.spectrum_list = []

    def run_acquisition(self) -> None:
        """Run the acquisition."""
        start = time.time()

        with Acquisition(show_display=False) as acq:  # type: ignore
            event_stack = multi_d_acquisition_events(
                num_time_points=self.num_time_points,
                xy_positions=self.xy_positions,  # type: ignore
                position_labels=self.labels,  # type: ignore
                order="pt",
            )
            print("Event stack:")
            print(event_stack)
            events = []
            for _event in event_stack:  # type: ignore
                for i in range(self.n_averages):
                    __event = deepcopy(_event)
                    __event["axes"]["avg_index"] = i
                    events.append(__event)
            print("Events:")
            print(events)

            for _, event in enumerate(events):
                future = acq.acquire(event)

                if self.shutter and (event["axes"]["avg_index"] == 0):
                    # open shutter before first image series
                    self._set_shutter_open_safe(is_open=True)

                print(f"Acquiring image {event["axes"]["avg_index"] + 1}/{self.n_averages}")
                result = future.await_image_saved(None, return_image=True, return_metadata=True)
                if result is None:
                    print("Error: No image or metadata returned.")
                    continue
                image, metadata = result
                self.process_image(image, metadata)  # type: ignore

                """
                Because time_interval_s does not work properly in PycroManager
                (see https://github.com/micro-manager/pycro-manager/issues/733), we manually
                implement the delay here. There are likely issues with this, e.g. there should be no
                 delay when moving to a new position, but this does a basic timelapse
                """
                is_final_in_average = event["axes"]["avg_index"] == self.n_averages - 1
                if (self.time_interval_s > 0) and is_final_in_average:
                    time.sleep(self.time_interval_s)

                if self.shutter and is_final_in_average:
                    # close shutter after last image in series
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
