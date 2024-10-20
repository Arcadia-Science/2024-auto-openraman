from tkinter import Button, Checkbutton, Entry, IntVar, Label

import matplotlib
import numpy as np
import pylab as pl
from pycromanager import Core, Studio
from scipy.signal import medfilt

''' getting current ROI from pycromanager
from pycromanager import Studio
studio = Studio(convert_camel_case=False)
snap_manager = studio.get_snap_live_manager()
cur_image = snap_manager.get_display().get_image_plus()
roi = cur_image.get_roi()
roi.get_bounds().x
161
roi.get_bounds().y
155
roi.get_bounds().width
'''
# Ensure TKAgg is used for matplotlib
matplotlib.use("TKAgg")

# Initialize the Micro-Manager core
core = Core()
print(core)
studio = Studio(convert_camel_case=False)

fig, ax = pl.subplots()
x = np.linspace(0, 10, 200)
y = np.zeros_like(x)  # Placeholder for y data
line, = ax.plot(x, y)
canvas = fig.canvas.get_tk_widget()

# Variables to hold y-axis bounds and control options
y_min, y_max = None, None
roi = None
autoscale = IntVar(value=1)  # Default to autoscale on
reverse_y = IntVar(value=0)   # Default to no reverse
apply_median_filter = IntVar(value=0)  # Default to no median filter


def update_from_camera():
    """Acquire an image using pycromanager and update the shared image data."""
    current_image = {"data": None}
    try:
        tagged_image = core.get_tagged_image()
        image_array = np.reshape(
            tagged_image.pix,
            newshape=[-1, tagged_image.tags["Height"], tagged_image.tags["Width"]],
        )
        # Update the shared image data (take the average across y-axis)
        current_image["data"] = image_array.mean(axis=1).squeeze()

    except Exception as e:
        print(f"Error acquiring image: {e}")
        current_image["data"] = None
    return current_image


def anim():
    ci = update_from_camera()  # Update image data from the camera
    if ci["data"] is not None:
        # Use the image data from the camera for the plot
        y = ci["data"]

        global roi
        if roi is not None:
            # NOTE: X not currently used; see x_data below
            y = y[roi['x']:roi['x']+roi['width']]
        # Reverse the y data if the checkbox is checked
        if reverse_y.get() == 1:
            y = y[::-1]

        # Apply median filter if the checkbox is checked
        if apply_median_filter.get() == 1:
            try:
                kernel_size = int(entry_kernel_size.get())
                # Apply median filter with the given kernel size
                y = medfilt(y, kernel_size=kernel_size)
            except ValueError:
                print("Invalid kernel size. Please enter a valid integer.")
            except Exception as e:
                print(f"Error applying median filter: {e}")

        x_data = np.linspace(0, len(y), len(y))
        line.set_data(x_data, y)
        ax.set_xlim(0, len(y))
        global y_min, y_max

        # Check if autoscale is enabled
        if autoscale.get() == 1:
            ax.set_ylim(y.min(), y.max())
        else:
            if y_min is not None and y_max is not None:
                ax.set_ylim(y_min, y_max)
            else:
                ax.set_ylim(y.min(), y.max())

    fig.canvas.draw()
    canvas.after(50, anim)


def set_y_bounds():
    """Set the y-axis bounds based on user input."""
    global y_min, y_max
    try:
        y_min = float(entry_min.get())
        y_max = float(entry_max.get())
        print(f"Y bounds set to: [{y_min}, {y_max}]")
    except ValueError:
        print("Invalid input for y bounds.")

def update_roi():
    # getting current ROI from pycromanager
    global roi
    snap_manager = studio.get_snap_live_manager()
    cur_image = snap_manager.get_display().get_image_plus()
    if cur_image is not None:
        ij_roi = cur_image.get_roi()
        if ij_roi is not None:
            x = ij_roi.get_bounds().x
            y = ij_roi.get_bounds().y
            width = ij_roi.get_bounds().width
            height = ij_roi.get_bounds().height
            print(f"Updated ROI: x={x}, y={y}, width={width}, height={height}")
            roi = {"x": x, "y": y, "width": width, "height": height}
        else:
            print("No ROI found in the current image.")
    else:
        print("No image found in the current display.")


# Add controls directly in the main window
Label(canvas.master, text="Y Min:").pack()
entry_min = Entry(canvas.master)
entry_min.pack()

Label(canvas.master, text="Y Max:").pack()
entry_max = Entry(canvas.master)
entry_max.pack()

b_set_bounds = Button(canvas.master, text="Set Y Bounds", command=set_y_bounds)
b_set_bounds.pack()

# Add the autoscale checkbox
autoscale_checkbox = Checkbutton(canvas.master, text="Y Autoscale", variable=autoscale)
autoscale_checkbox.pack()

# Add the use ROI button
b_update_roi = Button(canvas.master, text="Update ROI", command=update_roi)
b_update_roi.pack()

# Add the reverse y checkbox
reverse_checkbox = Checkbutton(canvas.master, text="Reverse Y", variable=reverse_y)
reverse_checkbox.pack()

# Add the median filter checkbox and kernel size entry
median_checkbox = Checkbutton(canvas.master, text="Apply Median Filter", variable=apply_median_filter)
median_checkbox.pack()

Label(canvas.master, text="Kernel Size:").pack()
entry_kernel_size = Entry(canvas.master)
entry_kernel_size.insert(0, "3")  # Default kernel size
entry_kernel_size.pack()

# Start the animation automatically
anim()

pl.show()
