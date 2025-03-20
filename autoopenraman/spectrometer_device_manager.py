# Device Manager to initialize and communicate with devices

AVAILABLE_SPECTROMETERS = ["wasatch", "openraman"]


class SpectrometerDeviceManager:
    def __init__(self):
        self.device = None

    def initialize(self, device):
        """
        Initialize a device based on its type.
        :param device: String specifying the device type ("DeviceA" or "DeviceB").
        """
        device = device.lower()
        if device == AVAILABLE_SPECTROMETERS[0]:
            from autoopenraman.wasatch_spectrometer import WasatchSpectrometer

            self.device = WasatchSpectrometer()
        elif device == AVAILABLE_SPECTROMETERS[1]:
            from autoopenraman.openraman_spectrometer import OpenRamanSpectrometer

            self.device = OpenRamanSpectrometer()
        else:
            raise ValueError(f"Unsupported device type: {device}")
        print(f"Initialized {device}")
        return self.device
