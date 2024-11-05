import os
from pathlib import Path

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots


class SpectrumPlotter:
    def __init__(self, input_path: Path):
        """Initialize the SpectrumPlotter.

        Uses Plotly to display spectra of a single CSV file or directory.

        Args:
            input_path (Path): The path to the CSV file or directory containing CSV files.
        """
        self.input_path = input_path
        self.csv_files = self._get_csv_files()

    def _get_csv_files(self) -> list[Path]:
        """Retrieve CSV files from the input path."""
        if self.input_path.is_dir():
            return [file for file in self.input_path.glob("*.csv")]
        elif self.input_path.is_file() and self.input_path.suffix == ".csv":
            return [self.input_path]
        else:
            print("Invalid input. Please provide a CSV file or a directory containing CSV files.")
            return []

    def run(self) -> None:
        """Plot the discovered CSV files using Plotly."""
        if not self.csv_files:
            print("No CSV files found.")
            return

        fig = make_subplots(rows=1, cols=1)
        for csv_file in self.csv_files:
            df = pd.read_csv(csv_file)
            # Assuming the first column is the X-axis and the second column is the Y-axis
            x_col = df.columns[0]
            y_col = df.columns[1]
            trace = go.Scatter(
                x=df[x_col], y=df[y_col], mode="lines", name=os.path.basename(csv_file)
            )
            fig.add_trace(trace)

        fig.update_layout(title="Spectrum Plot", xaxis_title=x_col, yaxis_title=y_col)
        fig.show()
