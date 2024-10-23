import argparse
import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots

def plot_csv(csv_files):
    fig = make_subplots(rows=1, cols=1)
    for csv_file in csv_files:
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
    
    fig.update_layout(title='CSV Data Plot', xaxis_title='X', yaxis_title='Y')
    fig.show()

def main():
    parser = argparse.ArgumentParser(description="Plot CSV files using Plotly.")
    parser.add_argument('input', type=str, help="Path to a CSV file or a directory of CSV files.")
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        csv_files = [os.path.join(args.input, f) for f in os.listdir(args.input) if f.endswith('.csv')]
    elif os.path.isfile(args.input) and args.input.endswith('.csv'):
        csv_files = [args.input]
    else:
        print("Invalid input. Please provide a CSV file or a directory containing CSV files.")
        return

    if csv_files:
        plot_csv(csv_files)
    else:
        print("No CSV files found.")

if __name__ == "__main__":
    main()
