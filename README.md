
# AutoOpenRaman

This repo contains a Python package called `autoopenraman`.

This package uses Micro-Manager and Pycro-Manager to interface with the OpenRaman spectrometer. It provides a UI for spectrum visualization and uses the Pycro-Manager backend to control additional hardware.

## Installation

```bash
pip install autoopenraman
```

## Usage

After installation, the package can be used with the command-line interface. The package provides a command-line interface with the following commands:

- `autoopenraman live`: Acquisition in live mode
- `autoopenraman acq`: Acquisition across multiple times/positions

For details on running, see the help message for each command:

```bash
autoopenraman live --help
autoopenraman acq --help
```

### Running tests with no hardware connected

To run the tests, first copy the configuration file template to your home directory:

On Mac:

```bash
cp .sample_autoopenraman_profile.yml ~/.autoopenraman_profile.yml
```

On Windows:

```bash
copy .sample_autoopenraman_profile.yml %USERPROFILE%\.sample_autoopenraman_profile.yml
```

Then, ensure that Micro-Manager is running with the default configuration (`MMConfig_demo.cfg`). No devices need to be connected to run the tests.

Then, run the tests:

```bash
pytest -v
```
