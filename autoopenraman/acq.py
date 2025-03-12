import json
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
from pycromanager import Acquisition, Core, multi_d_acquisition_events
from PyQt5.QtWidgets import QApplication
from pyqtgraph import PlotWidget

from autoopenraman import config_profile
from autoopenraman.utils import extract_stage_positions, image_to_spectrum, write_spectrum

# Ensure there's a QApplication instance
_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)


class AcquisitionManager:
    def __init__(
        self,
        n_averages: int = 1,
        exp_path: Path = Path("data/"),
        position_file: Path | None = None,
        shutter: bool = False,
        num_time_points: int | None = None,
        time_interval_s: float = 0,
        randomize_stage_positions: bool = False,
        headless: bool = False,  # Add headless mode for testing
    ):
        """Initialize the AcquisitionManager.

        Args:
            n_averages (int): The number of spectra to average for each acquisition.
                The default is 1.
            exp_path (Path): The full path to save the spectra. The default is 'data/'.
            position_file (Path | None): The path to the JSON file containing the stage positions.
                If none, the stage positions are not used. The default is None.
            shutter (bool): If True, find the shutter device in MM (defined in profile)
                and close it between positions. The default is False (use auto-shutter).
            num_time_points (int | None): The number of time points in the acquisition.
                If None, only one acquisition is done. The default is None.
            time_interval_s (float): The time interval between acquisitions in seconds.
                The default is 0.
            randomize_stage_positions (bool): If True, the order of the positions will be
                randomized.
            headless (bool): If True, run without creating any GUI components.
                Useful for testing. The default is False.
        """

        self.n_averages = n_averages
        self.exp_path = Path(exp_path)
        self.position_file = position_file
        self.shutter = shutter

        self.num_time_points = num_time_points
        self.time_interval_s = time_interval_s
        self.headless = headless

        if position_file is not None:
            self.xy_positions, self.labels = extract_stage_positions(
                position_file, randomize_stage_positions
            )
        else:
            self.xy_positions = None
            self.labels = None

        self.spectrum_list = []

        # Create pyqtgraph plot widget only if not in headless mode
        if not self.headless:
            self.plot_widget = PlotWidget()
            self.plot_widget.setWindowTitle("Acquisition Spectrum")
            self.plot_widget.setLabel("left", "Intensity")
            self.plot_widget.setLabel("bottom", "Pixels")
            self.plot = self.plot_widget.plot(pen="b")  # Blue line for the plot
            self.plot_widget.show()

            # Initial dummy data
            self.x, self.y = [0], [0]
            self.plot.setData(self.x, self.y)
        else:
            # Dummy attributes for headless mode
            self.plot_widget = None
            self.plot = None

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
        """Set the shutter open safely.

        Checks shutter status before setting it and raises an error if it cannot be set.

        Args:
            is_open (bool): True to open the shutter, False to close it.
        """

        # also select the right shutter here!

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
        """Save the metadata to a JSON file.

        Args:
            _filename (str): Metadata filename.
            metadata (dict): The metadata to save.
        """

        # add the acquisition parameters to the metadata
        _metadata["Number of averages"] = self.n_averages
        _metadata["Stage position file"] = self.position_file
        _metadata["DateTime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        with open(self.exp_path / (_filename + ".json"), "w") as f:
            json.dump(_metadata, f)

    def process_image(self, image: np.ndarray, metadata: dict) -> None:
        """Process the acquired image.

        Args:
            image (np.ndarray): The acquired image as a 2D numpy array.
            metadata (dict): Image metadata from Micro-Manager.
        """
        print("process_image")

        position = metadata.get("PositionName", metadata.get("Position", "DefaultPos"))
        axes = metadata.get("Axes", {})
        time_point = axes.get("time", "DefaultTime")
        fname = f"pos_{position}_time_{time_point}"

        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        # Calculate running average
        running_avg = (
            np.mean(self.spectrum_list, axis=0) if len(self.spectrum_list) > 0 else img_spectrum
        )

        # Update the plot only if not in headless mode
        if not self.headless:
            # Update the plot data
            self.plot.setData(x, running_avg)

            # Set axis ranges
            self.plot_widget.setXRange(0, len(img_spectrum))
            self.plot_widget.setYRange(np.min(running_avg), np.max(running_avg))

            # Set title
            self.plot_widget.setTitle(fname)

            # Process events to update the UI
            QApplication.processEvents()

        # if this is the final spectrum in the average, save average spectrum and metadata
        if len(self.spectrum_list) == self.n_averages:
            write_spectrum(self.exp_path / (fname + ".csv"), x, running_avg)

            self._save_metadata(fname, metadata)

            self.spectrum_list = []

    def run_acquisition(self) -> None:
        """Run the acquisition."""
        start = time.time()

        # Make sure the plot widget is visible if not in headless mode
        if not self.headless and self.plot_widget:
            self.plot_widget.show()

            # Process events to ensure UI is updated
            QApplication.processEvents()

        with Acquisition(show_display=False) as acq:
            event_stack = multi_d_acquisition_events(
                num_time_points=self.num_time_points,
                xy_positions=self.xy_positions,
                position_labels=self.labels,
                order="pt",
            )
            print("Event stack:")
            print(event_stack)
            events = []
            for _event in event_stack:
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
                image, metadata = future.await_image_saved(
                    None, return_image=True, return_metadata=True
                )
                self.process_image(image, metadata)

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

        elapsed_time = time.time() - start
        print(f"Time elapsed: {elapsed_time:.2f} s")

        # Keep processing events while plot is visible only in non-headless mode
        if not self.headless and self.plot_widget and self._is_standalone():
            print("Acquisition complete. Close the plot window to exit.")
            while self.plot_widget.isVisible():
                QApplication.processEvents()

    def cleanup(self):
        """Close the plot widget and clean up."""
        if not self.headless and hasattr(self, "plot_widget") and self.plot_widget:
            self.plot_widget.close()

    # Try to determine if we're in a main script context or inside another application
    def _is_standalone(self):
        """Check if this is running as a standalone script (not in a larger application)."""
        if self.headless:
            return False

        # Try to determine if we're in a main script context or inside another application
        active_window = QApplication.instance().activeWindow()
        return active_window is None or active_window == self.plot_widget
