from tkinter import Button, Checkbutton, Entry, IntVar, Label
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pycromanager import Core, Studio
from scipy.signal import medfilt

# Ensure TKAgg is used for matplotlib
matplotlib.use("TKAgg")


class LiveModeManager:
    def __init__(self):
        # Initialize the Micro-Manager core
        self.core = Core()
        print(self.core)
        self.studio = Studio(convert_camel_case=False)

        # Initialize figure and plot
        self.fig, self.ax = plt.subplots()
        self.x = np.linspace(0, 10, 200)
        self.y = np.zeros_like(self.x)  # Placeholder for y data
        self.line, = self.ax.plot(self.x, self.y)
        self.canvas = self.fig.canvas.get_tk_widget()

        # Variables to hold y-axis bounds and control options
        self.y_min, self.y_max = None, None
        self.roi = None
        self.autoscale = IntVar(value=1)  # Default to autoscale on
        self.reverse_y = IntVar(value=0)   # Default to no reverse
        self.apply_median_filter = IntVar(value=0)  # Default to no median filter

        # Set up the UI controls
        self.setup_controls()


    def setup_controls(self):
        # Add controls directly in the main window
        Label(self.canvas.master, text="Y Min:").pack()
        self.entry_min = Entry(self.canvas.master)
        self.entry_min.pack()

        Label(self.canvas.master, text="Y Max:").pack()
        self.entry_max = Entry(self.canvas.master)
        self.entry_max.pack()

        Button(self.canvas.master, text="Set Y Bounds", command=self.set_y_bounds).pack()

        # Add the autoscale checkbox
        Checkbutton(self.canvas.master, text="Y Autoscale", variable=self.autoscale).pack()

        # Add the use ROI button
        Button(self.canvas.master, text="Update ROI", command=self.update_roi).pack()

        # Add the reverse y checkbox
        Checkbutton(self.canvas.master, text="Reverse Y", variable=self.reverse_y).pack()

        # Add the median filter checkbox and kernel size entry
        Checkbutton(self.canvas.master, text="Apply Median Filter", variable=self.apply_median_filter).pack()

        Label(self.canvas.master, text="Kernel Size:").pack()
        self.entry_kernel_size = Entry(self.canvas.master)
        self.entry_kernel_size.insert(0, "3")  # Default kernel size
        self.entry_kernel_size.pack()

    def update_from_camera(self):
        """Acquire an image using pycromanager and update the shared image data."""
        current_image = {"data": None}
        # try:
        print("Snapping image...")
        self.core.snap_image()
        print("Image snapped with core {}", self.core)
        tagged_image = self.core.get_tagged_image()
        print(f"Tagged image acquired: {tagged_image.tags['Width']}x{tagged_image.tags['Height']}")
        image_array = np.reshape(
            tagged_image.pix,
            newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
        )
        # Update the shared image data (take the average across y-axis)
        current_image["data"] = image_array.mean(axis=1).squeeze()

        '''except Exception as e:
            print(f"Error acquiring image: {e}")
            # print stack
            e.with_traceback(e.__traceback__)
            current_image["data"] = None'''
        return current_image

    def run(self):
        ci = self.update_from_camera()  # Update image data from the camera
        if ci["data"] is not None:
            y = ci["data"]

            if self.roi is not None:
                y = y[self.roi['x']:self.roi['x']+self.roi['width']]
            # Reverse the y data if the checkbox is checked
            if self.reverse_y.get() == 1:
                y = y[::-1]

            # Apply median filter if the checkbox is checked
            if self.apply_median_filter.get() == 1:
                try:
                    kernel_size = int(self.entry_kernel_size.get())
                    y = medfilt(y, kernel_size=kernel_size)
                except ValueError:
                    print("Invalid kernel size. Please enter a valid integer.")
                except Exception as e:
                    print(f"Error applying median filter: {e}")

            x_data = np.linspace(0, len(y), len(y))
            self.line.set_data(x_data, y)
            self.ax.set_xlim(0, len(y))

            # Check if autoscale is enabled
            if self.autoscale.get() == 1:
                self.ax.set_ylim(y.min(), y.max())
            else:
                if self.y_min is not None and self.y_max is not None:
                    self.ax.set_ylim(self.y_min, self.y_max)
                else:
                    self.ax.set_ylim(y.min(), y.max())

        self.fig.canvas.draw()
        self.canvas.after(50, self.run)

    def set_y_bounds(self):
        """Set the y-axis bounds based on user input."""
        try:
            self.y_min = float(self.entry_min.get())
            self.y_max = float(self.entry_max.get())
            print(f"Y bounds set to: [{self.y_min}, {self.y_max}]")
        except ValueError:
            print("Invalid input for y bounds.")

    def update_roi(self):
        """Update the region of interest (ROI) based on the current image."""
        snap_manager = self.studio.get_snap_live_manager()
        cur_image = snap_manager.get_display().get_image_plus()
        if cur_image is not None:
            ij_roi = cur_image.get_roi()
            if ij_roi is not None:
                x = ij_roi.get_bounds().x
                y = ij_roi.get_bounds().y
                width = ij_roi.get_bounds().width
                height = ij_roi.get_bounds().height
                print(f"Updated ROI: x={x}, y={y}, width={width}, height={height}")
                self.roi = {"x": x, "y": y, "width": width, "height": height}
            else:
                print("No ROI found in the current image.")
        else:
            print("No image found in the current display.")


def main():
    live_mode_manager = LiveModeManager()
    live_mode_manager.run()
