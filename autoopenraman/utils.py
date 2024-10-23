import csv
import json
from typing import List, Tuple

import numpy as np


def write_spectrum(filename, x, y,
              header=["Pixel", "Intensity"]):
    """
    Write a 2-column CSV file of x and y

    Parameters:
    filename (str): The name of the file to write to.
    x (list): A list of pixel values.
    y (list): A list of intensity values corresponding to each pixel.
    """
    # Check if the lengths of the arrays match
    if len(x) != len(y):
        raise ValueError("The length of x and y arrays must be the same.")

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write the header
        writer.writerow(header)
        # Write the data rows
        for pixel, intensity in zip(x, y):
            writer.writerow([pixel, intensity])

def extract_stage_positions(file_path) -> Tuple[np.ndarray, List[str]]:
    # Load the JSON file
    with open(file_path) as file:
        data = json.load(file)

    # Extract the list of stage positions
    stage_positions = data['map']['StagePositions']['array']

    # Extract (X, Y) coordinates and labels
    coordinates = []
    labels = []

    for position in stage_positions:
        # Get the position array from DevicePositions
        device_positions = position['DevicePositions']['array']
        for device in device_positions:
            xy_position = device['Position_um']['array']
            coordinates.append(xy_position)
            labels.append(position['Label']['scalar'])

    # Convert coordinates to a numpy array of shape (N, 2) and labels to a numpy array
    coordinates_array = np.array(coordinates)

    return coordinates_array, labels

