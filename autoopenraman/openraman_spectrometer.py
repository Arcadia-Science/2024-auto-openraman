import numpy as np
from pycromanager import Core, Studio

from autoopenraman.spectrometer_device import AbstractSpectrometerDevice
from autoopenraman.utils import image_to_spectrum


class OpenRamanSpectrometer(AbstractSpectrometerDevice):
    def __init__(self):
        super().__init__(device_type="OpenRamanSpectrometer")

    def set_integration_time_ms(self, integ_time_ms):
        self._core.set_exposure(integ_time_ms)

    def set_laser_power_mW(self, laser_power_mW):
        print("Laser power setting not implemented for OpenRamanSpectrometer")
        pass

    def get_spectrum(self):
        self._core.snap_image()
        tagged_image = self._core.get_tagged_image()
        image_2d = np.reshape(
            tagged_image.pix,
            newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
        )
        spectrum = image_to_spectrum(image_2d)
        x = np.linspace(0, len(spectrum), len(spectrum))
        return x, spectrum

    def connect(self):
        try:
            self._studio = Studio()
            self._core = Core()
            return True
        except Exception as e:
            print(f"Error connecting to pycro-manager: {e}")
            return False

    def laser_on(self):
        print("Laser control not implemented for OpenRamanSpectrometer")

    def laser_off(self):
        print("Laser control not implemented for OpenRamanSpectrometer")
