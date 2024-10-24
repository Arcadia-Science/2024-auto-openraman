import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events

from autoopenraman.utils import image_to_spectrum, write_spectrum


class AcquisitionManager:
    def __init__(self, n_averages, save_dir):
        self.n_averages = n_averages
        self.save_dir = Path(save_dir)
        self.spectrum_list = []

        self.f, self.ax = plt.subplots()
        self.x = np.linspace(0, 10, 200)
        self.y = np.zeros_like(self.x)  # Placeholder for y data
        self.line, = self.ax.plot(self.x, self.y)

    def img_process_fn(self, image, metadata):
        print("img_process_fn")
        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        if len(self.spectrum_list) == self.n_averages:
            self.spectrum_list = np.array(self.spectrum_list)
            avg_spectrum = np.mean(self.spectrum_list, axis=0)

            fname = metadata.get('PositionName', metadata.get('Position', 'DefaultPos'))
            write_spectrum(self.save_dir / (fname + '.csv'), x, avg_spectrum)
            
            with open(self.save_dir / (fname + '.json'), 'w') as f:
                json.dump(metadata, f)

            self.spectrum_list = []

        # Update the plot
        '''
        self.line.set_data(x, img_spectrum)
        self.ax.set_xlim(0, len(img_spectrum))
        self.ax.set_ylim(np.min(img_spectrum), np.max(img_spectrum))
        self.f.canvas.draw()
        self.f.canvas.flush_events()
        '''
        return image, metadata

    def mock_acquisition(self):
        '''Mocks the Acquisition engine'''
        print('Mock acquisition')
        time.sleep(1)
        self.img_process_fn(np.random.random((100, 100)), {'PositionName': 'Mock Position'})

    def run_acquisition(self, xy_positions, labels):
        start = time.time()

        plt.show(block=False)
        plt.pause(0.1)

        # Mock acquisition (for testing purposes)
        # for i in range(5):
        #     self.mock_acquisition()

        with Acquisition(image_process_fn=self.img_process_fn,
                         debug=False,
                         show_display=False) as acq:  # directory='data/', name='test'
            events = multi_d_acquisition_events(
                num_time_points=self.n_averages,
                time_interval_s=0.5,
                xy_positions=xy_positions,
                position_labels=labels,
                order='pt')
            acq.acquire(events)

        print(f"Time elapsed: {time.time() - start:.2f} s")

def main(n_averages, xy_positions, labels, save_dir):
    acquisition_manager = AcquisitionManager(n_averages, save_dir)
    acquisition_manager.run_acquisition(xy_positions, labels)

if __name__ == '__main__':
    pass
