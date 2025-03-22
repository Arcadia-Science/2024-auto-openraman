import time

import numpy as np
from wasatch.DeviceID import DeviceID
from wasatch.RealUSBDevice import RealUSBDevice
from wasatch.WasatchBus import WasatchBus
from wasatch.WasatchDevice import WasatchDevice

from autoopenraman.spectrometer_device import AbstractSpectrometerDevice

LASER_WARMUP_SEC = 10
TEMPFILE = "spectrum.csv"  # for debugging


class WasatchSpectrometer(AbstractSpectrometerDevice):
    def __init__(self, use_sim=False):
        super().__init__()
        self.use_sim = use_sim

    def connect(self):  # -> bool
        if self.use_sim:
            device_id = DeviceID(label="MOCK:WP-00887:WP-00887-mock.json")
        else:
            bus = WasatchBus()
            device_id = bus.device_ids[0]
            device_id.device_type = RealUSBDevice(device_id)
            if not bus.device_ids:
                print("No Wasatch USB spectrometers found.")
                return False

        print(f"connecting to {device_id}")
        device = WasatchDevice(device_id)
        ok = device.connect()
        if not ok:
            print("can't connect to %s", device_id)
            return False

        self.settings = device.settings
        # in sim mode, wavenumbers array not assigned, so use wavelength array
        if self.use_sim:
            self.settings.wavenumbers = np.array([1 / (x + 1) for x in self.settings.wavelengths])
        self.fid = device.hardware
        if self.settings.wavelengths is None:
            print("script requires Raman spectrometer")
            return False

        print(
            "connected to %s %s with %d pixels (%.2f, %.2fnm) (%.2f, %.2fcm¹)"
            % (
                self.settings.eeprom.model,
                self.settings.eeprom.serial_number,
                self.settings.pixels(),
                self.settings.wavelengths[0],
                self.settings.wavelengths[-1],
                self.settings.wavenumbers[0],
                self.settings.wavenumbers[-1],
            )
        )

        self.current_power_mW = 0
        self.fid.set_laser_power_high_resolution(True)

        return True

    def get_integration_time_ms(self):
        return self.fid.get_integration_time_ms().data

    def set_integration_time_ms(self, integ_time_ms):
        print(f"setting integration time to {integ_time_ms}ms")
        self.fid.set_integration_time_ms(integ_time_ms)

    def get_laser_power_mW(self):
        return self.current_power_mW

    def set_laser_power_mW(self, laser_power_mW):
        print(f"setting laser power to {laser_power_mW}mW")
        self.current_power_mW = laser_power_mW
        self.fid.set_laser_power_mW(laser_power_mW)

    def laser_on(self):
        print("Enabling laser")
        self.fid.set_laser_enable(True)

        print(f"Waiting {LASER_WARMUP_SEC}sec for laser to warmup (required for MML)")
        time.sleep(LASER_WARMUP_SEC)

    def laser_off(self):
        print("Disabling laser")
        self.fid.set_laser_enable(False)
        print("Laser disabled")

    def get_spectrum(self):
        response = self.fid.get_line()
        if response and response.data:
            spectrum = response.data.spectrum

            # debugging
            with open(TEMPFILE, "w") as outfile:
                outfile.write("\n".join([f"{x:0.2f}" for x in spectrum]))

            return np.asarray(self.settings.wavenumbers), np.asarray(spectrum)
