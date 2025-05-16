import json
import logging
import time
import traceback
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from autoopenraman import configprofile
from autoopenraman.spectrometer_device_manager import SpectrometerDeviceManager
from autoopenraman.utils import write_spectrum


class SyncAcquisitionManager:
    def __init__(
        self,
        n_averages: int = 1,
        exp_path: Path = Path("data/"),
        sync_file: Path = Path("sync.txt"),
        wasatch_integration_time_ms=None,
        wasatch_laser_power_mW=None,
        wasatch_laser_warmup_sec=None,
        enable_logging: bool = False,
    ):
        """Initialize the SyncAcquisitionManager.

        Args:
            n_averages (int): The number of spectra to average for each acquisition.
                The default is 1.
            exp_path (Path): The full path to save the spectra. The default is 'data/'.
            sync_file (Path): Path to the sync file used for triggering acquisitions.
            wasatch_integration_time_ms: Integration time for Wasatch spectrometer in ms.
            wasatch_laser_power_mW: Laser power for Wasatch spectrometer in mW.
            wasatch_laser_warmup_sec: Laser warmup time for Wasatch spectrometer in seconds.
            enable_logging (bool): If True, enables detailed logging during acquisition.
        """

        # Set up logging if enabled
        self.enable_logging = enable_logging
        if enable_logging:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[
                    logging.FileHandler(Path(exp_path) / "sync_acquisition.log"),
                    logging.StreamHandler(),
                ],
            )
            self.logger = logging.getLogger("SyncAcquisitionManager")
            self.logger.info("Initializing SyncAcquisitionManager")
        else:
            self.logger = None

        self.n_averages = n_averages
        self.exp_path = Path(exp_path)
        self.sync_file = Path(sync_file)
        self.is_wasatch = "wasatch" in configprofile.spectrometer.lower()

        if self.enable_logging:
            self.logger.info(
                f"Parameters: n_averages={n_averages}, exp_path={exp_path}, sync_file={sync_file}"
            )
            self.logger.info(f"Using {'Wasatch' if self.is_wasatch else 'OpenRaman'} spectrometer")

        self.spectrum_list = []

        self.f, self.ax = plt.subplots()
        self.x, self.y = [0], [0]  # dummy values to initialize the plot
        (self.line,) = self.ax.plot(self.x, self.y, "k-")
        self.ax.set_xlabel("Wavenumber (cm-1)")
        self.ax.set_ylabel("Intensity")

        if self.is_wasatch:
            self.spectrometer_device = SpectrometerDeviceManager().initialize(
                configprofile.spectrometer,
                configprofile.simulate_spectrometer,
                laser_warmup_sec=wasatch_laser_warmup_sec,
            )
            if not self.spectrometer_device.connect():
                raise ValueError("Could not connect to spectrometer")
            if wasatch_integration_time_ms is not None:
                self.spectrometer_device.set_integration_time_ms(wasatch_integration_time_ms)
            else:
                raise ValueError("Wasatch integration time (--wasatch-integration-time-ms) not set")
            if wasatch_laser_power_mW is not None:
                self.spectrometer_device.set_laser_power_mW(wasatch_laser_power_mW)
            else:
                raise ValueError("Wasatch laser power (--wasatch-laser-power-mW) not set")
            self.spectrometer_device.laser_on()
        else:
            raise ValueError("Only Wasatch spectrometer is supported for synchronized acquisition")

    def _save_metadata(self, _filename: str, _metadata: dict) -> None:
        """Save the metadata to a JSON file.

        Args:
            _filename (str): Metadata filename.
            metadata (dict): The metadata to save.
        """

        metadata_file = self.exp_path / (_filename + ".json")
        if self.enable_logging:
            self.logger.info(f"Saving metadata to {metadata_file}")

        # add the acquisition parameters to the metadata
        _metadata["Number of averages"] = self.n_averages
        _metadata["DateTime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        # add the Wasatch-specific metadata
        _metadata["Wasatch"] = {}
        _metadata["Wasatch"]["Model"] = self.spectrometer_device.settings.eeprom.model
        _metadata["Wasatch"]["Wasatch integration time (ms)"] = (
            self.spectrometer_device.get_integration_time_ms()
        )
        _metadata["Wasatch"]["Wasatch laser power (mW)"] = (
            self.spectrometer_device.get_laser_power_mW()
        )
        _metadata["Wasatch"]["Wasatch laser warmup time (sec)"] = (
            self.spectrometer_device.laser_warmup_sec
        )

        with open(metadata_file, "w") as f:
            json.dump(_metadata, f)
            if self.enable_logging:
                self.logger.debug("Metadata saved successfully")

    def acquire_spectrum(self, name: str = "sync_acquisition") -> None:
        """Acquire and process spectra based on the number of averages.

        Args:
            name (str): Base name for saving the spectrum file.
        """
        if self.enable_logging:
            self.logger.info(f"Starting acquisition for {name}")

        self.spectrum_list = []
        metadata = {
            "PositionName": name,
            "DateTime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }

        # Get n_averages spectra and average them
        for i in range(self.n_averages):
            if self.enable_logging:
                self.logger.info(f"Acquiring spectrum {i+1}/{self.n_averages}")

            # Get spectrum from Wasatch spectrometer
            x, spectrum = self.spectrometer_device.get_spectrum()
            self.spectrum_list.append(spectrum)

            # Update the plot
            running_avg = np.mean(self.spectrum_list, axis=0)
            self.line.set_data(x, running_avg)
            self.ax.set_xlim([x.min(), x.max()])
            self.ax.set_ylim(np.min(running_avg), np.max(running_avg))
            self.ax.set_title(f"{name} - Average {i+1}/{self.n_averages}")
            self.f.canvas.draw()
            self.f.canvas.flush_events()

        # Save the averaged spectrum
        running_avg = np.mean(self.spectrum_list, axis=0)
        output_file = self.exp_path / (name + ".csv")
        if self.enable_logging:
            self.logger.info(f"Saving averaged spectrum to {output_file}")
        write_spectrum(output_file, x, running_avg)

        # Save metadata
        self._save_metadata(name, metadata)

        if self.enable_logging:
            self.logger.info(f"Completed acquisition for {name}")

    def run_sync_acquisition(self) -> None:
        """Run the synchronized acquisition loop.

        Waits for "ACQ" command in the sync file, acquires spectrum,
        and responds with "0" (started) and "1" (completed).
        """
        start = time.time()
        counter = 0

        if self.enable_logging:
            self.logger.info("Starting synchronized acquisition")

        plt.show(block=False)

        try:
            # Ensure the sync file exists
            if not self.sync_file.exists():
                with open(self.sync_file, "w") as f:
                    f.write("")
                if self.enable_logging:
                    self.logger.info(f"Created sync file: {self.sync_file}")

            running = True
            while running:
                # Check for ACQ command in sync file
                with open(self.sync_file) as f:
                    content = f.read().strip()

                if content == "ACQ":
                    # Clear the file and write 0 to acknowledge command received
                    with open(self.sync_file, "w") as f:
                        f.write("0")

                    if self.enable_logging:
                        self.logger.info("Received ACQ command, starting acquisition")

                    # Acquire spectrum
                    counter += 1
                    self.acquire_spectrum(f"sync_acquisition_{counter}")

                    # Write 1 to indicate acquisition complete
                    with open(self.sync_file, "w") as f:
                        f.write("1")

                    if self.enable_logging:
                        self.logger.info("Acquisition complete, ready for next command")

                # Small delay to prevent busy waiting
                time.sleep(0.1)

        except KeyboardInterrupt:
            if self.enable_logging:
                self.logger.info("Acquisition interrupted by user")
        except Exception as e:
            error_msg = f"Error during acquisition: {e}\n Time elapsed: {time.time() - start:.2f} s"
            traceback.print_exc()
            if self.enable_logging:
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
        finally:
            if self.is_wasatch:
                if self.enable_logging:
                    self.logger.info("Turning off Wasatch laser")
                self.spectrometer_device.laser_off()
            plt.close()
            complete_msg = f"Acquisition complete. Time elapsed: {time.time() - start:.2f} s"
            if self.enable_logging:
                self.logger.info(complete_msg)
