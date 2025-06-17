import sys

import click
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from autoopenraman.gui import AutoOpenRamanGUI


@click.command()
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Debug flag (used for testing): if set, will only run for a few seconds and quit",
)
def main(debug):
    """AutoOpenRaman - Acquisition and analysis GUI for OpenRaman spectrometer.

    Launches the unified GUI with both Live and Acquisition modes.
    Make sure Micro-Manager is running before executing!"""
    click.echo("Starting AutoOpenRaman GUI")
    app = QApplication(sys.argv)
    window = AutoOpenRamanGUI(debug)
    window.show()

    if debug:
        QTimer.singleShot(5000, app.quit)  # Run for 5 seconds and then quit

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
