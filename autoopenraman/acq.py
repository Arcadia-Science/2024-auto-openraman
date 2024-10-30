import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events
from collections.abc import Iterable
from autoopenraman.utils import image_to_spectrum, write_spectrum


class AcquisitionManager:
    def __init__(self, n_averages: int = 1,
                 save_dir: Path = Path('data/'),
                 xy_positions: Iterable | None = None,
                 labels: Iterable[str]| None = None):
        """Initialize the AcquisitionManager.
        
        Args:
            n_averages (int): The number of spectra to average for each acquisition. The default is 1.
            save_dir (Path): The directory to save the spectra. The default is 'data/'.
            xy_positions (Iterable): The XY positions to acquire from. The default is None (single position).
            labels (Iterable[str]): The labels for each position. The default is None (single position).
        """
        self.n_averages = n_averages
        self.save_dir = Path(save_dir)
        self.xy_positions = xy_positions
        self.n_positions = len(self.xy_positions) if xy_positions is not None else 1
        self.labels = labels
        self.spectrum_list = []

        self.f, self.ax = plt.subplots()
        self.x = np.linspace(0, 10, 200)
        self.y = np.zeros_like(self.x)  # Placeholder for y data
        self.line, = self.ax.plot(self.x, self.y)
        self.ax.set_xlabel("Pixels")
        self.ax.set_ylabel("Intensity")

    def process_image(self,
                      image: np.ndarray,
                      metadata: dict) -> None:
        """Process the acquired image.

        Args:
            image (np.ndarray): The acquired image as a 2D numpy array.
            metadata (dict): Image metadata from Micro-Manager.
        """
        print("process_image")
        fname = metadata.get('PositionName', metadata.get('Position', 'DefaultPos'))
        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        # if this is the final spectrum in the average, save the average
        if len(self.spectrum_list) == self.n_averages:
            self.spectrum_list = np.array(self.spectrum_list)
            avg_spectrum = np.mean(self.spectrum_list, axis=0)

            write_spectrum(self.save_dir / (fname + '.csv'), x, avg_spectrum)

            with open(self.save_dir / (fname + '.json'), 'w') as f:
                json.dump(metadata, f)

            self.spectrum_list = []

        # Update the plot
        avg_spectrum = np.mean(self.spectrum_list, axis=0) if len(self.spectrum_list) > 0 else img_spectrum
        self.line.set_data(x, avg_spectrum)
        self.ax.set_xlim(0, len(img_spectrum))
        self.ax.set_ylim(np.min(avg_spectrum), np.max(avg_spectrum))
        self.ax.set_title(fname)
        self.f.canvas.draw()
        self.f.canvas.flush_events()

    def run_acquisition(self) -> None:
        """Run the acquisition."""
        start = time.time()

        plt.show(block=False)
        plt.pause(0.1)

        with Acquisition(show_display=False) as acq:
            events = multi_d_acquisition_events(
                num_time_points=self.n_averages,
                time_interval_s=0,
                xy_positions=self.xy_positions,
                position_labels=self.labels,
                order='pt')
            print(events)

            for _,event in enumerate(events):
                future = acq.acquire(event)

                image,metadata = future.await_image_saved(event['axes'], return_image = True, return_metadata=True)
                self.process_image(image, metadata)


        print(f"Time elapsed: {time.time() - start:.2f} s")


def main(n_averages: int = 1,
         xy_positions: Iterable | None = None,
         labels: Iterable[str]| None = None,
         save_dir: Path = Path('data/')) -> None:
    """Main function called by the CLI to run the AcquisitionManager.

    Args:
        n_averages (int): The number of spectra to average for each acquisition.
        xy_positions (Iterable): The XY positions to acquire from.
        labels (Iterable[str]): The labels for each position.
        save_dir (Path): The directory to save the spectra.
    """
    acquisition_manager = AcquisitionManager(n_averages, save_dir, xy_positions, labels)
    acquisition_manager.run_acquisition()
