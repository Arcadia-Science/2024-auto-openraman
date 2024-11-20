import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Acquisition, Core, multi_d_acquisition_events

from autoopenraman import profile
from autoopenraman.utils import extract_stage_positions, image_to_spectrum, write_spectrum


class AcquisitionManager:
    def __init__(
        self,
        n_averages: int = 1,
        exp_path: Path = Path("data/"),
        position_file: Path | None = None,
        shutter: bool = False,
        randomize_stage_positions: bool = False,
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
            randomize_stage_positions (bool): If True, the order of the positions will be
                randomized.
        """

        self.n_averages = n_averages
        self.exp_path = Path(exp_path)
        self.position_file = position_file
        self.shutter = shutter

        if position_file is not None:
            self.xy_positions, self.labels = extract_stage_positions(
                position_file, randomize_stage_positions
            )
        else:
            self.xy_positions = None
            self.labels = None

        self.spectrum_list = []

        self.f, self.ax = plt.subplots()
        self.x, self.y = [0], [0]  # dummy values to initialize the plot
        (self.line,) = self.ax.plot(self.x, self.y)
        self.ax.set_xlabel("Pixels")
        self.ax.set_ylabel("Intensity")

        if self.shutter:
            self.core = Core()
            shutter_name = profile.shutter_name

            try:
                self.core.set_shutter_device(shutter_name)
            except ValueError as e:
                raise ValueError(f"Shutter device {shutter_name} not found in Micro-Manager") from e

            self.core.set_auto_shutter(False)

            # close shutter
            self._set_shutter_open_safe(open=False)

    def _set_shutter_open_safe(self, open: bool) -> None:
        """Set the shutter open safely.

        Checks shutter status before setting it and raises an error if it cannot be set.

        Args:
            open (bool): True to open the shutter, False to close it.
        """

        # also select the right shutter here!

        # if the shutter is already in the desired state, do nothing
        if self.core.get_shutter_open() == open:
            print(f"Shutter is already {'open' if open else 'closed'}")
            return

        # if the shutter is not in the desired state, try to set it
        self.core.set_shutter_open(open)

        # if the shutter is still not in the desired state, raise an error
        if self.core.get_shutter_open() != open:
            raise ValueError(f"Shutter could not be set to {'open' if open else 'closed'}")

        print(f"Shutter {'opened' if open else 'closed'}")

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
        fname = metadata.get("PositionName", metadata.get("Position", "DefaultPos"))
        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        # Update the plot
        running_avg = (
            np.mean(self.spectrum_list, axis=0) if len(self.spectrum_list) > 0 else img_spectrum
        )
        self.line.set_data(x, running_avg)
        self.ax.set_xlim(0, len(img_spectrum))
        self.ax.set_ylim(np.min(running_avg), np.max(running_avg))
        self.ax.set_title(fname)
        self.f.canvas.draw()
        self.f.canvas.flush_events()

        # if this is the final spectrum in the average, save average spectrum and metadata
        if len(self.spectrum_list) == self.n_averages:
            write_spectrum(self.exp_path / (fname + ".csv"), x, running_avg)

            self._save_metadata(fname, metadata)

            self.spectrum_list = []

    def run_acquisition(self) -> None:
        """Run the acquisition."""
        start = time.time()

        plt.show(block=False)

        with Acquisition(show_display=False) as acq:
            events = multi_d_acquisition_events(
                num_time_points=self.n_averages,
                time_interval_s=0,
                xy_positions=self.xy_positions,
                position_labels=self.labels.tolist(),
                order="pt",
            )
            print(events)

            for _, event in enumerate(events):
                future = acq.acquire(event)

                if self.shutter and (event["axes"]["time"] == 0):
                    # open shutter before first image in timeseries
                    self._set_shutter_open_safe(open=True)

                image, metadata = future.await_image_saved(
                    event["axes"], return_image=True, return_metadata=True
                )
                self.process_image(image, metadata)

                if self.shutter and (event["axes"]["time"] == self.n_averages - 1):
                    # close shutter after last image in timeseries
                    self._set_shutter_open_safe(open=False)

        print(f"Time elapsed: {time.time() - start:.2f} s")
