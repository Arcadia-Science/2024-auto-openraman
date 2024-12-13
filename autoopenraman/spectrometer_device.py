from abc import ABC, abstractmethod

import numpy as np


class AbstractSpectrometerDevice(ABC):
    """Abstract base class for all spectrometer devices.

    Implementations must override the following methods:
        set_integration_time_ms
        set_laser_power_mW
        get_spectrum
        connect
        laser_on
        laser_off

    If a device does not support a particular method, it should print a message.
    """

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def set_integration_time_ms(self, integ_time_ms) -> None:
        """Set acquisition integration time in milliseconds.

        Args:
            integ_time_ms (int): Integration time in milliseconds."""
        pass

    @abstractmethod
    def set_laser_power_mW(self, laser_power_mW) -> None:
        """Set laser power in milliwatts.

        Args:
            laser_power_mW (int): Laser power in milliwatts.
        """
        pass

    @abstractmethod
    def get_spectrum(self) -> tuple[np.ndarray, np.ndarray]:
        """Fetch spectrum from the spectrometer.

        Returns:
            tuple[np.ndarray, np.ndarray]: Tuple of x and y values of the spectrum.
                x ndarray is the 1-dimensional pixel or wavenumber values
                y ndarray is the 1-dimensional intensity values
        """
        pass

    @abstractmethod
    def connect(self):
        """Connect to the spectrometer device.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        pass

    @abstractmethod
    def laser_on(self):
        pass

    @abstractmethod
    def laser_off(self):
        pass
