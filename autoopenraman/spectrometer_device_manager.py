# Device Manager to initialize and communicate with devices
class SpectrometerDeviceManager:
    def __init__(self):
        self.device = None

    def initialize(self, device):
        """
        Initialize a device based on its type.
        :param device: String specifying the device type ("DeviceA" or "DeviceB").
        """
        if device == "WasatchSpectrometer":
            from wasatch_spectrometer import WasatchSpectrometer

            self.device = WasatchSpectrometer()
        elif device == "OpenRamanSpectrometer":
            from openraman_spectrometer import OpenRamanSpectrometer

            self.device = OpenRamanSpectrometer()
        else:
            raise ValueError(f"Unsupported device type: {device}")
        print(f"Initialized {self.device.device_type}")
        return self.device
