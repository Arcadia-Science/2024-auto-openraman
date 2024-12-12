import sys

import numpy as np
from pycromanager import Studio
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from pyqtgraph import PlotWidget
from scipy.signal import medfilt
from spectrometer_device_manager import SpectrometerDeviceManager


# Worker Thread for Image Acquisition
class SpectrometerAcquisition(QThread):
    data_acquired = pyqtSignal(np.ndarray)  # Signal to emit spectrum data

    def __init__(self, spectrometer):
        super().__init__()
        self.spectrometer = spectrometer
        self.running = True

    def run(self):
        while self.running:
            try:
                spectrum = self.spectrometer.get_spectrum()
                self.data_acquired.emit(spectrum)
            except Exception as e:
                print(f"Error snapping image: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# Main Application Class
class LiveModeManager(QMainWindow):
    def __init__(self, debug=False):
        super().__init__()

        self.debug = debug
        # Pycro-Manager Studio Initialization
        self._studio = Studio(convert_camel_case=True)

        # Main GUI Setup
        self.setWindowTitle("Live Mode Manager")
        self.setGeometry(100, 100, 800, 500)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Plot Widget
        self.plot_widget = PlotWidget()
        self.plot = self.plot_widget.plot()
        self.layout.addWidget(self.plot_widget)

        # Controls
        controls_layout = QHBoxLayout()

        # Column 1: Spectrometer Settings
        column1_layout = QVBoxLayout()
        column1_layout.addWidget(QLabel("Spectrometer Settings"))

        # Exposure Time Input
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("Exposure Time (ms):"))
        self.exposure_time_input = QLineEdit("100")
        self.exposure_time_input.returnPressed.connect(self.set_exposure_time)
        exposure_layout.addWidget(self.exposure_time_input)
        column1_layout.addLayout(exposure_layout)

        # Laser Power Input
        laser_power_layout = QHBoxLayout()
        laser_power_layout.addWidget(QLabel("Laser Power (mW):"))
        self.laser_power_input = QLineEdit("100")
        self.laser_power_input.returnPressed.connect(self.set_laser_power)
        laser_power_layout.addWidget(self.laser_power_input)
        column1_layout.addLayout(laser_power_layout)

        controls_layout.addLayout(column1_layout)

        # Column 2: Laser Control
        column2_layout = QVBoxLayout()
        column2_layout.addWidget(QLabel("Laser Control"))

        # Laser On/Off Toggle
        self.laser_on_btn = QPushButton("Laser On")
        self.laser_on_btn.setCheckable(True)
        self.laser_on_btn.clicked.connect(self.toggle_laser)
        column2_layout.addWidget(self.laser_on_btn)

        controls_layout.addLayout(column2_layout)

        # Column 3: Acquisition Control
        column3_layout = QVBoxLayout()
        column3_layout.addWidget(QLabel("Acquisition Control"))

        # Reverse X
        self.reverse_x = False
        self.reverse_x_check = QCheckBox("Reverse X")
        self.reverse_x_check.stateChanged.connect(self.toggle_reverse_x)
        column3_layout.addWidget(self.reverse_x_check)

        # Median Filter Checkbox
        self.median_filter_check = QCheckBox("Apply Median Filter")
        self.median_filter_check.stateChanged.connect(self.toggle_median_filter)
        column3_layout.addWidget(self.median_filter_check)

        # Start/Stop Button
        start_stop_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_acquisition)
        start_stop_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.stop_btn.setEnabled(False)
        start_stop_layout.addWidget(self.stop_btn)

        column3_layout.addLayout(start_stop_layout)

        controls_layout.addLayout(column3_layout)

        self.layout.addLayout(controls_layout)

        # Thread Setup
        self.worker = None
        self.apply_median_filter = False

        if self.debug:
            print("Debug mode enabled")
            self.start_acquisition()
            timer = QTimer()
            timer.singleShot(5000, self.stop_acquisition)

        # Initialize spectrometer
        self.spectrometer_device = SpectrometerDeviceManager().initialize("OpenRamanSpectrometer")
        if not self.spectrometer_device.connect():
            raise ValueError("Could not connect to spectrometer")

    def set_exposure_time(self):
        """Set the exposure time for the spectrometer."""
        exposure_time = int(self.exposure_time_input.text())
        self.spectrometer_device.set_integration_time_ms(exposure_time)

    def toggle_laser(self):
        """Toggle laser on/off."""
        if self.laser_on_btn.isChecked():
            self.spectrometer_device.laser_on()
            self.laser_on_btn.setText("Laser Off")
        else:
            self.spectrometer_device.laser_off()
            self.laser_on_btn.setText("Laser On")

    def set_laser_power(self):
        """Set the laser power for the spectrometer."""
        laser_power = int(self.laser_power_input.text())
        self.spectrometer_device.set_laser_power_mW(laser_power)

    def toggle_median_filter(self):
        """Toggle median filter application."""
        self.apply_median_filter = self.median_filter_check.isChecked()

    def toggle_reverse_x(self):
        """Toggle X-axis reversal."""
        self.reverse_x = self.reverse_x_check.isChecked()

    def start_acquisition(self):
        """Start the worker thread for live acquisition."""
        print("Starting acquisition...")
        self.worker = SpectrometerAcquisition(self.spectrometer_device)
        self.worker.data_acquired.connect(self.update_plot)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_acquisition(self):
        """Stop the worker thread."""
        if self.worker:
            self.worker.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        print("Stopped acquisition...")

    def update_plot(self, spectrum):
        """Update the plot with new spectrum data."""
        if self.apply_median_filter:
            spectrum = medfilt(spectrum, kernel_size=3)

        if self.reverse_x:
            spectrum = spectrum[::-1]

        x_data = np.linspace(0, len(spectrum), len(spectrum))
        self.plot.setData(x_data, spectrum)

    def closeEvent(self, event):
        """Handle window close event to stop worker thread."""
        if self.worker:
            self.worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiveModeManager()
    window.show()
    sys.exit(app.exec_())
