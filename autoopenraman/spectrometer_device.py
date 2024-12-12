from abc import ABC, abstractmethod


# Abstract base class for all devices
class AbstractSpectrometerDevice(ABC):
    def __init__(self, device_type):
        self.device_type = device_type

    @abstractmethod
    def set_integration_time_ms(self, integ_time_ms):
        pass

    @abstractmethod
    def set_laser_power_mW(self, laser_power_mW):
        pass

    @abstractmethod
    def get_spectrum(self):
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def laser_on(self):
        pass

    @abstractmethod
    def laser_off(self):
        pass


"""
# Example usage
def main():
    manager = DeviceManager()

    # Initialize DeviceA
    manager.initialize(device="DeviceA")
    device = manager.get_device()
    result = device.take_measurement()
    print(f"Measurement result from {device.device_type}: {result}")

    # Re-initialize with DeviceB
    manager.initialize(device="DeviceB")
    device = manager.get_device()
    result = device.take_measurement()
    print(f"Measurement result from {device.device_type}: {result}")

if __name__ == "__main__":
    main()
"""
