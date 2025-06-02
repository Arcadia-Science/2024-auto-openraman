# AutoOpenRaman

This repo contains a Python package called `autoopenraman`.

This package uses Micro-Manager and Pycro-Manager to interface with the OpenRaman spectrometer. It provides a UI for spectrum visualization and uses the Pycro-Manager backend to control additional hardware.

![neon-livemode-trimmed-cropped](https://github.com/user-attachments/assets/112d72d0-c514-4c67-b598-cf7b13f4f842)


## Installation

First, make sure you have [poetry](https://python-poetry.org/docs/#installing-with-pipx) installed.

Then, clone the repository, install dependencies, and install the package:
```bash
git clone https://github.com/Arcadia-Science/2024-auto-openraman
cd 2024-auto-openraman
conda create -n autoopenraman-dev python=3.12
conda activate autoopenraman-dev
poetry install --no-root --with dev
pip install -e .
```

## Usage

After installation, launch the application with:

```bash
autoopenraman
```

Optional flags:
- `autoopenraman --debug`: Runs in debug mode for testing (runs for 5 seconds then quits)

The GUI provides a unified interface where you can switch between:
- **Live Mode**: Real-time spectrum visualization with filtering options
- **Acquisition Mode**: Configure and run automated acquisitions across multiple positions

## Features

### Live Mode Features
- **Real-time visualization**: Continuous spectrum display from the spectrometer
- **Background subtraction**: Capture, store, and subtract background spectra to highlight sample features
- **Median filtering**: Apply configurable kernel size median filtering to reduce noise
- **X-axis reversal**: Option to reverse the x-axis for compatibility with different spectrometer orientations

### Acquisition Mode Features
- **Multi-position acquisition**: Acquire spectra at multiple stage positions defined in a Micro-Manager position list file
- **Spectra averaging**: Configurable number of acquisitions to average per position
- **Position randomization**: Option to randomize the order of stage positions during acquisition
- **Timelapse acquisition**: Configure multiple time points with specified intervals
- **Automatic file saving**: Saves spectra and metadata to CSV and JSON files

### Calibration Features
- **Wavenumber calibration**: Two-step calibration process using neon lamp and acetonitrile reference spectra
- **Save/load calibrations**: Save calibration for later use or load previously saved calibrations
- **Adjustable excitation wavelength**: Configure the excitation wavelength for accurate Raman shift calculation

## Hardware Requirements

- A computer running Windows (tested), macOS (tested), or Linux (not tested)
- [Micro-Manager 2.0](https://micro-manager.org/Micro-Manager_Nightly_Builds) (tested with v2.0.3-20241016)
- [OpenRAMAN spectrometer](https://www.open-raman.org/) camera, connected to the PC by USB
- Optional: XY stage for multi-position acquisition
- Optional: Shutter device for controlling laser exposure

### Running tests with no hardware connected

To run the tests, first copy the configuration file template to your home directory and rename it to `profile.yml`.

On Mac:

```bash
cp .sample_autoopenraman_profile.yml ~/autoopenraman/profile.yml
```

On Windows:

```bash
copy .sample_autoopenraman_profile.yml %USERPROFILE%\autoopenraman\profile.yml
```

Download the latest version of [Micro-Manager 2.0](https://micro-manager.org/Micro-Manager_Nightly_Builds) compatible with your OS. The package was built around `Micro-Manager 2.0.3-20241016` but should work with subsequent nightly builds.

Run Micro-Manager with the configuration `autoopenraman_mmconfig_demo.cfg` found in the root directory of this repo. No physical devices need to be connected to run the tests.

In Micro-Manager, go to Tools>Options and enable the checkbox "Run pycro-manager server on port 4827". You will only need to do this once.

Then, run the tests:

```bash
pytest -v
```

## Configuration

### Profile Configuration

AutoOpenRaman uses `profile.yml` to track hardware connections and configurations. The file is located in the `~/.autoopenraman` directory on Mac and Linux, and in `%USERPROFILE%\autoopenraman` on Windows.

The profile includes the following key settings:

```yaml
# Default environment (testing or deployment)
environment: testing

# Testing environment settings (uses simulated devices)
testing:
  save_dir: ~/autoopenraman/data
  shutter_name: DemoShutter

# Deployment environment settings (for real hardware)
deployment:
  save_dir: ~/experiments/raman_data
  shutter_name: ArduinoShutter  # Replace with your actual shutter device name
```

When using real hardware, it is recommended to set the environment to `deployment` in the `profile.yml` file and update the corresponding section with your hardware information.

Set `save_dir` to the default directory where you want to save the acquired spectra. This directory will be created if it does not exist.

If using a real shutter, set `shutter_name` to match the name of the shutter in Micro-Manager.

## Calibration Guide

AutoOpenRaman provides a two-step calibration process to convert from pixel coordinates to Raman shift (wavenumbers):

1. **Rough calibration** using a neon lamp spectrum to establish pixel-to-wavelength relationship
2. **Fine calibration** using acetonitrile reference spectrum to convert wavelengths to accurate Raman shifts

### Calibration Procedure

1. In the GUI, click the "Calibrate" button
2. Select a neon lamp reference spectrum file (CSV format)
3. Select an acetonitrile reference spectrum file (CSV format)
4. Enter the excitation laser wavelength (default: 532 nm)
5. Click "Calibrate" to perform the calibration
6. Use "Save Calibration" to save the calibration for future use

The software identifies peaks in these reference spectra and matches them to known reference values:
- Neon peaks at specific wavelengths (585.249 - 653.288 nm)
- Acetonitrile peaks at specific Raman shifts (918, 1376, 2249, 2942, 2999 cm⁻¹)

After calibration, you can switch between "Pixels" and "Wavenumbers (cm⁻¹)" display modes using the dropdown menu.

### Data Output Format

#### Spectrum Files
Spectra are saved in CSV format with either 2 or 3 columns:
- Without calibration: `Pixel, Intensity`
- With calibration: `Pixel, Wavenumber (cm⁻¹), Intensity`

#### Metadata Files
Each spectrum has an accompanying JSON metadata file with the same base filename (but `.json` extension) containing:

1. **Acquisition Parameters**:
   - `Number of averages`: Number of spectra averaged for each measurement
   - `Stage position file`: Path to the position list file used
   - `DateTime`: Timestamp of acquisition (YYYY-MM-DD HH:MM:SS)

2. **Timelapse Information**:
   - `NumTimePoints`: Number of time points in the timelapse
   - `TimeIntervalSeconds`: Interval between time points in seconds

3. **Processing Parameters**:
   - `MedianFilter`: Settings for filtering (`Applied` boolean and `KernelSize`)
   - `ReverseX`: Whether the X-axis was reversed

4. **Calibration Information**:
   - `Applied`: Whether calibration was applied
   - `ExcitationWavelength`: Laser wavelength in nm (if calibrated)

5. **Position Information**:
   - `PositionName`: Name of the stage position from MM position list
   - Time point information from the acquisition

This metadata provides complete context for interpreting each spectrum and reproducing acquisition settings.

### Managing dependencies

We use poetry to manage dependencies. To add a new dependency, use the following command:

```bash
poetry add some-package
```

To add a new development dependency, use the following command:

```bash
poetry add -G dev some-dev-package
```

To update a dependency, use the following command:

```bash
poetry update some-package
```

Whenever you add or update a dependency, poetry will automatically update both `pyproject.toml` and the `poetry.lock` file. Make sure to commit the changes to these files to the repo.
