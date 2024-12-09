import sys

import numpy as np
from pycromanager import Core, Studio
from PyQt5.QtCore import QThread, pyqtSignal
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

from autoopenraman.utils import image_to_spectrum


# Worker Thread for Image Acquisition
class CameraWorker(QThread):
    data_acquired = pyqtSignal(np.ndarray)  # Signal to emit spectrum data

    def __init__(self):
        super().__init__()
        self._core = Core()
        self.running = True

    def run(self):
        while self.running:
            try:
                # Simulate slow acquisition
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
class LiveModeManager(QMainWindow):
    def __init__(self):
        super().__init__()

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

        # Reverse X
        self.reverse_x = False
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
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_acquisition)
        controls_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)

        self.layout.addLayout(controls_layout)

        # Thread Setup
        self.worker = None
        self.apply_median_filter = False

    def toggle_median_filter(self):
        """Toggle median filter application."""
        self.apply_median_filter = self.median_filter_check.isChecked()

    def toggle_reverse_x(self):
        """Toggle X-axis reversal."""
        self.reverse_x = self.reverse_x_check.isChecked()

    def start_acquisition(self):
        """Start the worker thread for live acquisition."""
        self.worker = CameraWorker()
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

    def update_plot(self, spectrum):
        """Update the plot with new spectrum data."""
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
