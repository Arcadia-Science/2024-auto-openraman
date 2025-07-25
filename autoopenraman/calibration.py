import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.signal import find_peaks, medfilt

# Calibration Constants
# Source: https://physics.nist.gov/PhysRefData/Handbook/Tables/neontable2.htm
NEON_PEAKS_NM = np.array(
    [
        585.249,
        588.189,
        594.483,
        607.434,
        609.616,
        614.306,
        616.359,
        621.728,
        626.649,
        630.479,
        633.443,
        638.299,
        640.225,
        650.653,
        653.288,
    ]
)

ACETONITRILE_PEAKS_CM1 = np.array([918, 1376, 2249, 2942, 2999])

# Default parameters
DEFAULT_EXCITATION_WAVELENGTH_NM = 532.0
DEFAULT_KERNEL_SIZE = 5
DEFAULT_ROUGH_CALIBRATION_RESIDUALS_THRESHOLD = 1e0
DEFAULT_FINE_CALIBRATION_RESIDUALS_THRESHOLD = 1e2
MIN_PEAK_PROMINENCE = 0.05


def find_n_most_prominent_peaks(
    intensities: np.ndarray, n_peaks: int = 15, kernel_size: int = DEFAULT_KERNEL_SIZE
) -> np.ndarray:
    """
    Find the n most prominent peaks in a spectrum.

    Parameters:
        intensities: np.ndarray - The intensities array
        n_peaks: int - Number of peaks to find
        kernel_size: int - Size of the median filter kernel

    Returns:
        np.ndarray - Indices of the n most prominent peaks
    """
    # Apply median filter to smooth the data
    smoothed_intensities = medfilt(intensities, kernel_size=kernel_size)

    # Find peaks
    peaks, properties = find_peaks(smoothed_intensities, prominence=MIN_PEAK_PROMINENCE)

    # If no peaks found or fewer than requested, return what we found
    if len(peaks) == 0:
        return np.array([])

    if len(peaks) < n_peaks:
        return peaks

    # Sort peaks by prominence and take the n most prominent
    prominences = properties["prominences"]
    sorted_indices = np.argsort(prominences)[::-1]  # Descending order
    return peaks[sorted_indices[:n_peaks]]


def rescale_axis_via_least_squares_fit(
    source_points: np.ndarray, target_points: np.ndarray, all_source_points: np.ndarray
) -> tuple[np.ndarray, float]:
    """
    Rescale source points to target points using least squares fit.

    Parameters:
        source_points: np.ndarray - The source points to map from
        target_points: np.ndarray - The target points to map to
        all_source_points: np.ndarray - All source points to transform

    Returns:
        Tuple[np.ndarray, float] - Transformed points and sum of squared residuals
    """
    # Ensure we have enough points for mapping
    if len(source_points) < 2 or len(target_points) < 2:
        raise ValueError("Need at least 2 points for mapping")

    if len(source_points) != len(target_points):
        raise ValueError("Number of source and target points must match")

    # Perform polynomial fit (linear)
    coeffs = np.polyfit(source_points, target_points, 1)

    # Transform all source points
    transformed_points = np.polyval(coeffs, all_source_points)

    # Calculate residuals for the fit points
    predicted_points = np.polyval(coeffs, source_points)
    residuals = float(np.sum((predicted_points - target_points) ** 2))

    return transformed_points, residuals


def calculate_raman_shift(
    emission_wavelengths_nm: np.ndarray,
    excitation_wavelength_nm: float = DEFAULT_EXCITATION_WAVELENGTH_NM,
) -> np.ndarray:
    """
    Calculate Raman shift in wavenumbers (cm^-1) from wavelengths.

    Parameters:
        emission_wavelengths_nm: np.ndarray - Emission wavelengths in nm
        excitation_wavelength_nm: float - Excitation wavelength in nm

    Returns:
        np.ndarray - Raman shift in wavenumbers (cm^-1)
    """
    # Convert wavelengths to wavenumbers using the Raman formula
    nm_to_cm = 1e7
    return (1.0 / excitation_wavelength_nm - 1.0 / emission_wavelengths_nm) * nm_to_cm


class RamanCalibrator:
    """
    Class to handle the calibration of Raman spectra from pixel to wavenumber.
    """

    def __init__(
        self,
        excitation_wavelength_nm: float = DEFAULT_EXCITATION_WAVELENGTH_NM,
        kernel_size: int = DEFAULT_KERNEL_SIZE,
        rough_calibration_residuals_threshold: float = (
            DEFAULT_ROUGH_CALIBRATION_RESIDUALS_THRESHOLD
        ),
        fine_calibration_residuals_threshold: float = DEFAULT_FINE_CALIBRATION_RESIDUALS_THRESHOLD,
    ):
        """
        Initialize the calibrator.

        Parameters:
            excitation_wavelength_nm: Excitation laser wavelength in nm
            kernel_size: Size of median filter kernel for peak finding
            rough_calibration_residuals_threshold: Threshold for rough calibration residuals
            fine_calibration_residuals_threshold: Threshold for fine calibration residuals
        """
        self.excitation_wavelength_nm = excitation_wavelength_nm
        self.kernel_size = kernel_size
        self.rough_calibration_residuals_threshold = rough_calibration_residuals_threshold
        self.fine_calibration_residuals_threshold = fine_calibration_residuals_threshold

        # Calibration data
        self.pixel_indices = np.array([])  # Original pixel indices initialized as an empty array
        self.rough_calibration_wavelengths = None  # Wavelengths from rough calibration
        self.wavenumbers = None  # Final calibrated wavenumbers
        self.calibration_coefficients: dict[str, Optional[np.ndarray]] = {
            "rough": None,  # Coefficients for pixel to wavelength
            "fine": None,  # Coefficients for rough wavenumber to final wavenumber
        }

    def calibrate(self, neon_spectrum: np.ndarray, acetonitrile_spectrum: np.ndarray) -> np.ndarray:
        """
        Perform two-step calibration using (first) neon and (second) acetonitrile spectra.

        Parameters:
            neon_spectrum: np.ndarray - Intensity values from neon lamp
            acetonitrile_spectrum: np.ndarray - Intensity values from acetonitrile sample

        Returns:
            np.ndarray - Calibrated wavenumbers for the original pixel indices
        """
        # Create pixel indices
        self.pixel_indices = np.arange(len(neon_spectrum))

        # Step 1: Rough calibration using neon peaks
        self.rough_calibration_wavelengths, rough_residuals = self._rough_calibration(neon_spectrum)

        # Validate rough calibration
        if rough_residuals > self.rough_calibration_residuals_threshold:
            raise ValueError(f"Rough calibration failed with residuals: {rough_residuals}")

        # Calculate rough wavenumbers from rough wavelengths
        rough_wavenumbers = calculate_raman_shift(
            self.rough_calibration_wavelengths, self.excitation_wavelength_nm
        )

        # Step 2: Fine calibration using acetonitrile peaks
        self.wavenumbers, fine_residuals = self._fine_calibration(
            acetonitrile_spectrum, rough_wavenumbers
        )

        # Validate fine calibration
        if fine_residuals > self.fine_calibration_residuals_threshold:
            raise ValueError(f"Fine calibration failed with residuals: {fine_residuals}")

        return self.wavenumbers

    def _rough_calibration(self, neon_spectrum: np.ndarray) -> tuple[np.ndarray, float]:
        """
        Perform rough calibration using neon spectrum to map pixels to wavelengths.

        Parameters:
            neon_spectrum: np.ndarray - Neon lamp intensity values

        Returns:
            Tuple[np.ndarray, float] - Wavelengths array and residuals
        """
        # Find prominent peaks in the neon spectrum
        peak_indices = find_n_most_prominent_peaks(
            neon_spectrum, n_peaks=len(NEON_PEAKS_NM), kernel_size=self.kernel_size
        )

        if len(peak_indices) < 2:
            raise ValueError(f"Not enough peaks found in neon spectrum. Found {len(peak_indices)}")

        # Sort peak indices and use the most appropriate number of peaks
        peak_indices = np.sort(peak_indices)
        num_peaks = min(len(peak_indices), len(NEON_PEAKS_NM))
        peak_indices = peak_indices[:num_peaks]
        neon_reference = NEON_PEAKS_NM[:num_peaks]

        # Map pixel indices to wavelengths using least squares fit
        wavelengths, residuals = rescale_axis_via_least_squares_fit(
            peak_indices, neon_reference, self.pixel_indices
        )

        # Store the coefficients (for potential saving/loading)
        self.calibration_coefficients["rough"] = np.polyfit(peak_indices, neon_reference, 1)

        return wavelengths, residuals

    def _fine_calibration(
        self, acetonitrile_spectrum: np.ndarray, rough_wavenumbers: np.ndarray
    ) -> tuple[np.ndarray, float]:
        """
        Perform fine calibration using acetonitrile spectrum.

        Parameters:
            acetonitrile_spectrum: np.ndarray - Acetonitrile sample intensity values
            rough_wavenumbers: np.ndarray - Rough wavenumbers from rough calibration

        Returns:
            Tuple[np.ndarray, float] - Calibrated wavenumbers and residuals
        """
        # Find prominent peaks in the acetonitrile spectrum
        peak_indices = find_n_most_prominent_peaks(
            acetonitrile_spectrum, n_peaks=len(ACETONITRILE_PEAKS_CM1), kernel_size=self.kernel_size
        )

        if len(peak_indices) < 2:
            raise ValueError(
                f"Not enough peaks found in acetonitrile spectrum. Found {len(peak_indices)}"
            )

        # Get the rough wavenumbers at the peak positions
        rough_peak_wavenumbers = rough_wavenumbers[peak_indices]

        # Sort peak wavenumbers and use the most appropriate number of peaks
        sorted_indices = np.argsort(rough_peak_wavenumbers)
        peak_indices = peak_indices[sorted_indices]
        rough_peak_wavenumbers = rough_peak_wavenumbers[sorted_indices]

        num_peaks = min(len(peak_indices), len(ACETONITRILE_PEAKS_CM1))
        peak_indices = peak_indices[:num_peaks]
        rough_peak_wavenumbers = rough_peak_wavenumbers[:num_peaks]
        acetonitrile_reference = ACETONITRILE_PEAKS_CM1[:num_peaks]

        # Map rough wavenumbers to reference wavenumbers using least squares fit
        fine_wavenumbers, residuals = rescale_axis_via_least_squares_fit(
            rough_peak_wavenumbers, acetonitrile_reference, rough_wavenumbers
        )

        # Store the coefficients (for potential saving/loading)
        self.calibration_coefficients["fine"] = np.polyfit(
            rough_peak_wavenumbers, acetonitrile_reference, 1
        )

        return fine_wavenumbers, residuals

    def apply_calibration(self, pixel_indices: np.ndarray) -> np.ndarray:
        """
        Apply existing calibration to new pixel indices.

        Parameters:
            pixel_indices: np.ndarray - Pixel indices to calibrate

        Returns:
            np.ndarray - Calibrated wavenumbers
        """
        if (
            self.calibration_coefficients["rough"] is None
            or self.calibration_coefficients["fine"] is None
        ):
            raise ValueError("Calibration has not been performed. Call calibrate() first.")

        # Apply rough calibration to get wavelengths
        wavelengths = np.polyval(self.calibration_coefficients["rough"], pixel_indices)

        # Convert to rough wavenumbers
        rough_wavenumbers = calculate_raman_shift(wavelengths, self.excitation_wavelength_nm)

        # Apply fine calibration
        wavenumbers = np.polyval(self.calibration_coefficients["fine"], rough_wavenumbers)

        return wavenumbers

    def save_calibration(self, file_path: Path) -> None:
        """
        Save the calibration data to a file.

        Parameters:
            file_path: Path - Path to save the calibration data
        """
        if (
            self.calibration_coefficients["rough"] is None
            or self.calibration_coefficients["fine"] is None
        ):
            raise ValueError("Calibration has not been performed. Call calibrate() first.")

        calibration_data = {
            "excitation_wavelength_nm": self.excitation_wavelength_nm,
            "coefficients": self.calibration_coefficients,
            "pixel_indices": self.pixel_indices,
            "wavelengths": self.rough_calibration_wavelengths,
            "wavenumbers": self.wavenumbers,
        }

        with open(file_path, "wb") as f:
            pickle.dump(calibration_data, f)

    def load_calibration(self, file_path: Path) -> None:
        """
        Load calibration data from a file.

        Parameters:
            file_path: Path - Path to the calibration file
        """
        with open(file_path, "rb") as f:
            calibration_data = pickle.load(f)

        self.excitation_wavelength_nm = calibration_data["excitation_wavelength_nm"]
        self.calibration_coefficients = calibration_data["coefficients"]
        self.pixel_indices = calibration_data["pixel_indices"]
        self.rough_calibration_wavelengths = calibration_data["wavelengths"]
        self.wavenumbers = calibration_data["wavenumbers"]
