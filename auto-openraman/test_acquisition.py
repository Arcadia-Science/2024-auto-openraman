import json
from typing import List, Tuple

import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events


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
            if device['Device']['scalar'] == 'XY':
                xy_position = device['Position_um']['array']
                coordinates.append(xy_position)
                labels.append(position['Label']['scalar'])

    # Convert coordinates to a numpy array of shape (N, 2) and labels to a numpy array
    coordinates_array = np.array(coordinates)
    # labels_array = np.array(labels)

    return coordinates_array, labels

xy_positions, labels = extract_stage_positions('data/stage_positions/PositionList.pos')

with Acquisition(directory='data/', name='test') as acq:
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        xy_positions=xy_positions,
        position_labels=labels,
        order='tp')
    acq.acquire(events)