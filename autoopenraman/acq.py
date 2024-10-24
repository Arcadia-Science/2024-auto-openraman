import argparse
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events
from autoopenraman.utils import extract_stage_positions, write_spectrum

global n_averages, save_dir

f, ax = plt.subplots()
x = np.linspace(0, 10, 200)
y = np.zeros_like(x)  # Placeholder for y data
line, = ax.plot(x, y)

def img_process_fn(image, metadata):
    print("img_process_fn")
    img_spectrum = image.mean(axis=1).squeeze()

    x = np.linspace(0,len(img_spectrum)-1, len(img_spectrum))

    if not hasattr(img_process_fn, "spectrum_list"):
        img_process_fn.spectrum_list = []
    img_process_fn.spectrum_list.append(img_spectrum)

    global n_averages, save_dir
    '''Note: this assumes all traces to be averaged will be taken in order'''
    if len(img_process_fn.spectrum_list) == n_averages:
        img_process_fn.spectrum_list = np.array(img_process_fn.spectrum_list)
        avg_spectrum = np.mean(img_process_fn.spectrum_list, axis=0)

        if 'PositionName' in metadata.keys():
            fname = metadata['PositionName']
        elif 'Position' in metadata.keys():
            fname = metadata['Position']
        else:
            fname = 'DefaultPos'
        write_spectrum(save_dir / (fname + '.csv'), x, avg_spectrum)
        # save metadata
        with open(save_dir / (fname + '.json'), 'w') as f:
            json.dump(metadata, f)
        img_process_fn.spectrum_list = []
    # update the plot
    '''
    line.set_data(x, img_spectrum)
    ax.set_xlim(0, len(img_spectrum))
    ax.set_ylim(np.min(img_spectrum), np.max(img_spectrum))
    f.canvas.draw()
    f.canvas.flush_events()
    '''
    return image, metadata


def mock_acquisition():
    '''mocks the Acquisition engine'''

    print('Mock acquisition')
    time.sleep(1)
    img_process_fn(np.random.random((100,100)), {'PositionName': 'Mock Position'})

def main(_n_averages,
        xy_positions,
        labels,
        _save_dir):
    
    global n_averages, save_dir
    n_averages = _n_averages
    save_dir = _save_dir
    start = time.time()

    plt.show(block=False)
    plt.pause(0.1)

    # mock acquisition
    # for i in range(5):
    #     mock_acquisition()
    with Acquisition(image_process_fn=img_process_fn,
                     debug=False,
                     show_display=False) as acq:  # directory='data/', name='test'
        events = multi_d_acquisition_events(
            num_time_points = n_averages,
            time_interval_s = 0.5,
            xy_positions=xy_positions,
            position_labels=labels,
            order='pt')
        acq.acquire(events)

    print(f"Time elapsed: {time.time() - start:.2f} s")

if __name__ == '__main__':
    pass