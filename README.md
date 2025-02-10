
# AutoOpenRaman

This repo contains a Python package called `autoopenraman`.

This package uses Micro-Manager and Pycro-Manager to interface with the OpenRaman spectrometer. It provides a UI for spectrum visualization and uses the Pycro-Manager backend to control additional hardware.

## Installation

First, make sure you have [poetry](https://python-poetry.org/docs/#installing-with-pipx) installed.

Then, clone the repository and install the package:
```bash
git clone https://github.com/Arcadia-Science/2024-auto-openraman
conda create -n autoopenraman-dev python=3.12
conda activate autoopenraman-test
poetry install --no-root --with dev,docs,build
pip install -e .
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
