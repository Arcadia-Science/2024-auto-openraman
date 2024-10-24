import argparse
import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path

class SpectrumPlotter:
    def __init__(self, input_path):
        self.input_path = input_path
        self.csv_files = self._get_csv_files()

    def _get_csv_files(self):
        """Retrieve CSV files from the input path."""
        if self.input_path.is_dir():
            return [file for file in self.input_path.glob('*.csv')]
        elif self.input_path.is_file() and self.input_path.suffix == '.csv':
            return [self.input_path]
        else:
            print("Invalid input. Please provide a CSV file or a directory containing CSV files.")
            return []

    def run(self):
        """Plot the CSV files using Plotly."""
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
                x=df[x_col],
                y=df[y_col],
                mode='lines',
                name=os.path.basename(csv_file)
            )
            fig.add_trace(trace)
        
        fig.update_layout(title='Spectrum Plot', xaxis_title='X', yaxis_title='Intensity')
        fig.show()

def main(file_or_dir):
    plotter = SpectrumPlotter(file_or_dir)
    plotter.run()
