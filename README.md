
# AutoOpenRaman

This repo contains a Python package called `autoopenraman`.

This package uses Micro-Manager and Pycro-Manager to interface with the OpenRaman spectrometer. It provides a UI for spectrum visualization and uses the Pycro-Manager backend to control additional hardware.

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
cp .sample_autoopenraman_profile.yml ~/.config/autoopenraman/profile.yml
```

On Windows:

```bash
copy .sample_autoopenraman_profile.yml %USERPROFILE%\autoopenraman\profile.yml
```

Download the latest version of [Micro-Manager 2.0](https://micro-manager.org/Micro-Manager_Nightly_Builds) compatible with your OS. The package was built around `Micro-Manager 2.0.3-20241016` but should work with subsequent nightly builds.

Run Micro-Manager with the configuration `autoopenraman_mmconfig_demo.cfg` found in the root directory of this repo. No physical devices need to be connected to run the tests.

In Micro-Manager, go to Tools>Options and enable the checkbox "Run pycro-manager server on port 4827". You will only need to do this once.

If this is your first time running

Then, run the tests:

```bash
pytest -v
```

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
