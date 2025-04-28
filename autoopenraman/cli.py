import sys

import click
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from autoopenraman.gui import AutoOpenRamanGUI


@click.group()
def cli():
    """Aquisition and analysis with AutoOpenRaman.

    Use this to start the acquisition or live mode.
    Make sure Micro-Manager is running before executing!"""
    pass


@cli.command()
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Debug flag (used for testing): if set, will only run for a few seconds and quit",
)
def gui(debug):
    """Start the unified GUI with both Live and Acquisition modes"""
    click.echo("Starting AutoOpenRaman GUI")
    app = QApplication(sys.argv)
    window = AutoOpenRamanGUI(debug)
    window.show()

    if debug:
        QTimer.singleShot(5000, app.quit)  # Run for 5 seconds and then quit

    sys.exit(app.exec_())


def main():
    # By default, run the unified GUI
    if len(sys.argv) == 1:
        gui(False)
    else:
        cli()


if __name__ == "__main__":
    main()
