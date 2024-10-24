import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events

from autoopenraman.utils import image_to_spectrum, write_spectrum


class AcquisitionManager:
    def __init__(self, n_averages, save_dir, xy_positions, labels):
        self.n_averages = n_averages
        self.save_dir = Path(save_dir)
        self.xy_positions = xy_positions
        self.n_positions = len(xy_positions) if xy_positions is not None else 1
        self.labels = labels
        self.spectrum_list = []

        self.f, self.ax = plt.subplots()
        self.x = np.linspace(0, 10, 200)
        self.y = np.zeros_like(self.x)  # Placeholder for y data
        self.line, = self.ax.plot(self.x, self.y)

    def img_process_fn(self, image, metadata):
        print("img_process_fn")
        fname = metadata.get('PositionName', metadata.get('Position', 'DefaultPos'))
        img_spectrum = image_to_spectrum(image)

        x = np.linspace(0, len(img_spectrum) - 1, len(img_spectrum))
        self.spectrum_list.append(img_spectrum)

        if len(self.spectrum_list) == self.n_averages:
            self.spectrum_list = np.array(self.spectrum_list)
            avg_spectrum = np.mean(self.spectrum_list, axis=0)

            write_spectrum(self.save_dir / (fname + '.csv'), x, avg_spectrum)
            
            with open(self.save_dir / (fname + '.json'), 'w') as f:
                json.dump(metadata, f)

            self.spectrum_list = []

        # Update the plot
        
        
        avg_spectrum = np.mean(self.spectrum_list, axis=0) if len(self.spectrum_list) > 0 else img_spectrum
        self.line.set_data(x, avg_spectrum)
        self.ax.set_xlim(0, len(img_spectrum))
        self.ax.set_ylim(np.min(avg_spectrum), np.max(avg_spectrum))
        self.ax.set_title(fname)
        self.f.canvas.draw()
        self.f.canvas.flush_events()
        
        # return image, metadata

    def mock_acquisition(self):
        '''Mocks the Acquisition engine'''
        print('Mock acquisition')
        time.sleep(1)
        self.img_process_fn(np.random.random((100, 100)), {'PositionName': 'Mock Position'})

    def run_acquisition(self):
        start = time.time()

        plt.show(block=False)
        plt.pause(0.1)

        # Mock acquisition (for testing purposes)
        # for i in range(5):
        #     self.mock_acquisition()
        
        '''
        n_trials = 0
        if self.n_positions > 1:
            n_trials = self.n_positions * self.n_averages
            mock_positions = [{'PositionName': f'Pos{i}'} for i in range(self.n_positions)]
        else:
            n_trials = self.n_averages
            mock_positions = [{'PositionName': 'DefaultPos'}]
        '''
        with Acquisition(show_display=False) as acq:
            events = multi_d_acquisition_events(
                num_time_points=self.n_averages,
                time_interval_s=[0.5]*self.n_averages,
                xy_positions=self.xy_positions,
                position_labels=self.labels,
                order='pt')
            print(events)

            for i,event in enumerate(events):
                future = acq.acquire(event)
                image = future.await_image_saved(event['axes'], return_image = True, return_metadata=False)
                metadata = event['axes']

                # temporary workaround due to https://github.com/micro-manager/pycro-manager/issues/799
                metadata['PositionName'] = metadata.get('position', 'DefaultPos')
                
                self.img_process_fn(image, metadata)


        print(f"Time elapsed: {time.time() - start:.2f} s")

def main(n_averages, xy_positions, labels, save_dir):
    acquisition_manager = AcquisitionManager(n_averages, save_dir, xy_positions, labels)
    acquisition_manager.run_acquisition()

if __name__ == '__main__':
    pass
