from tkinter import Button, Checkbutton, Entry, IntVar, Label

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from pycromanager import Core, Studio
from scipy.signal import medfilt

from autoopenraman.utils import image_to_spectrum

matplotlib.use("TKAgg")


class LiveModeManager:
    """Live mode acquisition manager.

    Attributes:
        _core (Core): Pycro-Manager Core
        _studio (Studio): Pycro-Manager Studio
        fig (Figure): Matplotlib figure for real-time plotting
        ax (Axes): Matplotlib axes for real-time plotting
        x (np.ndarray): X-axis data
        y (np.ndarray): Y-axis data
        line (Line2D): Line object for the plot
        y_min (float): Minimum value for y-axis
        y_max (float): Maximum value for y-axis
        roi (dict): ROI selection from Micro-Manager live view
        autoscale (IntVar): Y autoscale
        reverse_x (IntVar): Reverse X-axis in case camera image is transposed
    """

    def __init__(self):
        """Initialize the LiveModeManager.

        Args:
            None
        """
        self._core = Core()
        self._studio = Studio(convert_camel_case=False)

        # Initialize figure and plot
        self.fig, self.ax = plt.subplots()
        self.x = np.linspace(0, 10, 200)
        self.y = np.zeros_like(self.x)  # Placeholder for y data
        (self.line,) = self.ax.plot(self.x, self.y)
        self.ax.set_title("Live Mode")
        self.ax.set_xlabel("Pixels")
        self.ax.set_ylabel("Intensity")

        # Variables to hold y-axis bounds and control options
        self.y_min, self.y_max = None, None
        self.roi = None
        self.autoscale = IntVar(value=1)  # Default to autoscale on
        self.reverse_x = IntVar(value=0)  # Default to no reverse
        self.apply_median_filter = IntVar(value=0)  # Default to no median filter

        # Set up the UI controls
        self.setup_controls()

    def run(self, debug: bool = False) -> None:
        """Run the live mode animation.

        Args:
            debug (bool): If True, run the animation for 10 seconds and exit. Used for testing.
            The default is False.
        """
        self.ani = FuncAnimation(
            self.fig,
            self.update_frame,
            interval=50,
            frames=100 if debug else None,
            cache_frame_data=False,
            repeat=False,
        )
        if debug:
            # for debugging/testing, show the plot for 10 seconds and exit successfully
            plt.show(block=False)
            plt.pause(10)
            plt.close("all")
        else:
            plt.show()

    def setup_controls(self) -> None:
        """Set up the UI controls."""
        Label(self.fig.canvas.get_tk_widget().master, text="Y Min:").pack()
        self.entry_min = Entry(self.fig.canvas.get_tk_widget().master)
        self.entry_min.pack()

        Label(self.fig.canvas.get_tk_widget().master, text="Y Max:").pack()
        self.entry_max = Entry(self.fig.canvas.get_tk_widget().master)
        self.entry_max.pack()

        Button(
            self.fig.canvas.get_tk_widget().master, text="Set Y Bounds", command=self.set_y_bounds
        ).pack()

        Checkbutton(
            self.fig.canvas.get_tk_widget().master, text="Y Autoscale", variable=self.autoscale
        ).pack()

        Button(
            self.fig.canvas.get_tk_widget().master, text="Update ROI", command=self.update_roi
        ).pack()

        Checkbutton(
            self.fig.canvas.get_tk_widget().master, text="Reverse X", variable=self.reverse_x
        ).pack()

        Checkbutton(
            self.fig.canvas.get_tk_widget().master,
            text="Apply Median Filter",
            variable=self.apply_median_filter,
        ).pack()

        Label(self.fig.canvas.get_tk_widget().master, text="Kernel Size:").pack()
        self.entry_kernel_size = Entry(self.fig.canvas.get_tk_widget().master)
        self.entry_kernel_size.insert(0, "3")  # Default kernel size
        self.entry_kernel_size.pack()

    def get_spectrum_from_camera(self) -> np.ndarray:
        """Acquire an image from the camera and convert to spectrum by averaging along x axis.

        Returns:
            np.ndarray: The acquired spectrum.
        """
        try:
            self._core.snap_image()
            tagged_image = self._core.get_tagged_image()
            image_2d = np.reshape(
                tagged_image.pix,
                newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
            )
        except Exception as e:
            print("Error acquiring image!")
            raise e

        # Convert the 2D image to a spectrum
        return image_to_spectrum(image_2d)

    def update_frame(self, _) -> None:
        """Update single frame of the animation."""
        _spectrum = self.get_spectrum_from_camera()  # Update image data from the camera

        if self.roi is not None:
            _spectrum = _spectrum[self.roi["x"] : self.roi["x"] + self.roi["width"]]
        # Reverse the y data if the checkbox is checked
        if self.reverse_x.get() == 1:
            _spectrum = _spectrum[::-1]

        # Apply median filter if the checkbox is checked
        if self.apply_median_filter.get() == 1:
            try:
                kernel_size = int(self.entry_kernel_size.get())
                _spectrum = medfilt(_spectrum, kernel_size=kernel_size)
            except ValueError:
                print("Invalid kernel size. Please enter a valid integer.")
            except Exception as e:
                print(f"Error applying median filter: {e}")

        x_data = np.linspace(0, len(_spectrum), len(_spectrum))
        self.line.set_data(x_data, _spectrum)
        self.ax.set_xlim(0, len(_spectrum))

        # Check if autoscale is enabled
        if self.autoscale.get() == 1:
            self.ax.set_ylim(_spectrum.min(), _spectrum.max())
        else:
            if self.y_min is not None and self.y_max is not None:
                self.ax.set_ylim(self.y_min, self.y_max)
            else:
                self.ax.set_ylim(_spectrum.min(), _spectrum.max())

        self.fig.canvas.draw()

    def set_y_bounds(self) -> None:
        """Set the y-axis bounds based on user input.

        Raises:
            ValueError: If the input is not a valid float.
        """
        try:
            self.y_min = float(self.entry_min.get())
            self.y_max = float(self.entry_max.get())
            print(f"Y bounds set to: [{self.y_min}, {self.y_max}]")
        except ValueError:
            print("Invalid input for y bounds.")

    def update_roi(self) -> None:
        """Update the ROI based on the current selection in Micro-Manager."""
        snap_manager = self._studio.get_snap_live_manager()
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
