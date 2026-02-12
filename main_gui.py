from datetime import datetime
import tkinter as tk
from tkinter import ttk
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure
import numpy as np
from dwfconstants import *
import sys
from math import log10

if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

"""
Main GUI class
"""


class Gui:
    def __init__(self, root, title="T1 measurements"):
        # =GUI=
        self.root = root
        self.root.title(title)
        self.root.resizable(height=False, width=False)  # make window non-resizable
        # associate entries and scales with object for callback references
        # device status entry
        self.status = tk.StringVar(root, value="Not connected")
        # minimum dark time
        self.td_min = tk.DoubleVar(root, value=1)
        self.scale_td_min = None
        self.entry_td_min = None
        # maximum dark time
        self.td_max = tk.DoubleVar(root, value=1)
        self.scale_td_max = None
        self.entry_td_max = None
        # number of data points
        self.dps = tk.DoubleVar(root, value=10)
        self.scale_dps = None
        self.entry_dps = None
        # tree view for running log and status messages
        self.tree_running_log = None

        # startup code for creating and rendering app
        self.populate()

        # =AD2=
        self.hdwf = c_int()  # AD2 handle
        self.laser_channel = c_int(0)  # wavegen channel 1
        self.lia_channel = c_int(1)  # wavegen channel 2
        self.find_device()  # look for an AD2 on startup

        # =T1 measurements=
        self.sequences = []

    """
    Generate a pseudo-logarithmic integer space for generating dark times with different sample sizes
    """

    def gen_log_space(self, td_min, td_max, n):
        result = [td_min]
        # return 1 if bad n
        if n <= 1:
            return result

        for i in range(n - 1):
            td_curr = round(10 ** (i * log10(td_max) / (n - 1)))
            # check if dark time is repeating last value and increment it if yes
            if td_curr - result[-1] >= 1:
                result.append(td_curr + td_min)
            else:
                result.append(result[-1] + 1 + td_min)
        result.append(td_max)  # add last value manually to eliminate offset
        return result


    """
    Connect to AD2 or show that it is not connected
    """

    def find_device(self):
        # TODO: make a button associated with the find function
        # TODO: add disconnect handler
        # version required for operation
        version = create_string_buffer(16)
        dwf.FDwfGetVersion(version)
        print("DWF Version: " + str(version.value))

        # define behavior on close (0 = run, 1 = stop, 2 = shutdown)
        dwf.FDwfParamSet(DwfParamOnClose, c_int(0))

        # open device and get interface reference
        if dwf.FDwfDeviceOpen(c_int(-1), byref(self.hdwf)):
            self.log_message("AD2", "Connection", f"Connected to AD2, DWF Version {str(version.value)}")
            self.status.set("Connected")
        else:
            szerr = create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(szerr)
            self.log_message("AD2", "Connection", szerr.value)

        # disable auto config for better performance
        dwf.FDwfDeviceAutoConfigureSet(self.hdwf, c_int(0))

    """
    Generate sequences for pulsing
    """

    def t1_generate_sequences(self):
        # TODO: add channel syncing and LIA sequences
        # constants
        pattern_size = 4096  # fixed pattern buffer size
        f_pattern = 1 / (pattern_size * self.td_min.get())  # set frequency of the whole pattern
        # fixed minimum dark time to pulse width ratio
        min_td = 1  # dark time (in buffer slots)
        max_td = int(self.td_max.get() * f_pattern)  # TODO: verify formula
        pw = 5  # pulse width (in buffer slots)
        all_tds = self.gen_log_space(td_min=min_td, td_max=max_td, n=self.dps.get()) # pseudo-logspace of dark times

        # make pattern
        td = min_td
        # loop for all data points
        for curr_td in all_tds:
            pattern = (c_double * pattern_size)(0)  # initialize C-style zero array
            for i in range(0, pw):
                pattern[i] = 1  # cancellation pulse
                pattern[int(i + (pattern_size / 2))] = 1  # initialization pulse
                pattern[int(i + pw + td + (pattern_size / 2))] = 1  # readout pulse


    """
    Set value of Tkinter entry
    """

    def update_entry(self, e, value):
        if e is None:
            raise NameError(f"Entry is not initialized yet, value {value} not updated")
        e.delete(0, tk.END)
        e.insert(0, value)
        return

    """
    Logger function for GUI log
    """

    def log_message(self, source, status, value):
        if self.tree_running_log is None:
            raise NameError("Tree is not initialized yet")
        else:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tree_running_log.insert('', tk.END, text=timestamp, values=(source, status, value))

    """
    Callback for updating minimum dark time variable and entry based on slider
    """

    def callback_s_td_min(self, event):
        if self.scale_td_min != self.td_min.get():
            self.td_min.set(self.scale_td_min.get())
            self.update_entry(self.entry_td_min, self.td_min.get())

    """
    Callback for updating maximum dark time variable and entry based on slider
    """

    def callback_s_td_max(self, event):
        if self.scale_td_max != self.td_max.get():
            self.td_max.set(self.scale_td_max.get())
            self.update_entry(self.entry_td_max, self.td_max.get())

    """
    Callback for updating number of data points variable and entry based on slider
    """

    def callback_s_dps(self, event):
        if self.scale_dps.get() != self.dps.get():
            self.dps.set(self.scale_dps.get())
            self.update_entry(self.entry_dps, self.dps.get())

    """
       Callback for updating minimum dark time variable and slider based on entry
       """

    def callback_e_td_min(self, event):
        if float(self.entry_td_min.get()) != self.td_min.get():
            self.td_min.set(self.entry_td_min.get())
            self.scale_td_min.set(self.td_min.get())

    """
    Callback for updating maximum dark time variable and slider based on entry
    """

    def callback_e_td_max(self, event):
        if float(self.entry_td_max.get()) != self.td_max.get():
            self.td_max.set(self.entry_td_max.get())
            self.scale_td_max.set(self.td_max.get())

    """
    Callback for updating number of data points variable and slider based on entry
    """

    def callback_e_dps(self, event):
        if float(self.entry_dps.get()) != self.dps.get():
            self.dps.set(self.entry_dps.get())
            self.scale_dps.set(self.dps.get())

    """
    Put GUI objects in app
    Should only be called by the constructor
    """

    def populate(self):
        # create frames
        lf_devices = ttk.Labelframe(self.root, text="Devices")
        lf_status = ttk.Labelframe(self.root, text="Test status")
        lf_inputs = ttk.Labelframe(self.root, text="T1 parameters")
        lf_data = ttk.Labelframe(self.root, text="Test data")

        # put frames in app
        lf_devices.grid(row=0, column=0, padx=5, pady=5, sticky=("N", "W", "E", "S"))
        lf_status.grid(row=1, column=0, padx=5, pady=5, sticky=("N", "W", "E", "S"))
        lf_inputs.grid(row=2, column=0, padx=5, pady=5, sticky=("N", "W", "E", "S"))
        lf_data.grid(row=0, column=1, rowspan=3, padx=5, pady=5, sticky=("N", "W", "E", "S"))

        # =DEVICE FRAME=
        # create labels
        label_name = ttk.Label(lf_devices, text="Device name")
        label_status = ttk.Label(lf_devices, text="Device status")

        # put labels in app
        label_name.grid(row=0, column=0, sticky="W", padx=5, pady=5)
        label_status.grid(row=1, column=0, sticky="W", padx=5, pady=5)

        # create entries
        entry_name = ttk.Entry(lf_devices)
        self.update_entry(entry_name, "Analog Discovery 2")
        entry_name.config(state="readonly")
        entry_status = ttk.Entry(lf_devices, state="readonly", textvariable=self.status)

        # put entries in app
        entry_name.grid(row=0, column=1, sticky="W", padx=5, pady=5)
        entry_status.grid(row=1, column=1, sticky="W", padx=5, pady=5)

        # =STATUS FRAME=
        # create tree
        self.tree_running_log = ttk.Treeview(lf_status, columns=("Source", "Status", "Value"))

        # label columns
        self.tree_running_log.heading("#0", text="Time")
        self.tree_running_log.heading("Source", text="Source")
        self.tree_running_log.heading("Status", text="Status")
        self.tree_running_log.heading("Value", text="Value")

        # set column size
        self.tree_running_log.column("#0", minwidth=10, width=70)
        self.tree_running_log.column("Source", minwidth=10, width=70)
        self.tree_running_log.column("Status", minwidth=10, width=70)
        self.tree_running_log.column("Value", minwidth=10, width=210)

        # put tree in app
        self.tree_running_log.grid(row=0, column=0, sticky=("N", "W", "E", "S"), padx=5, pady=5)

        # log first status message
        self.log_message("GUI", "Startup", "GUI created")

        # =INPUT FRAME=
        # create labels
        label_td_min = ttk.Label(lf_inputs, text="Minimum dark time")
        label_td_max = ttk.Label(lf_inputs, text="Maximum dark time")
        label_dps = ttk.Label(lf_inputs, text="Number of data points")

        # put labels in app
        label_td_min.grid(row=0, column=0, sticky="W", padx=5, pady=5)
        label_td_max.grid(row=1, column=0, sticky="W", padx=5, pady=5)
        label_dps.grid(row=2, column=0, sticky="W", padx=5, pady=5)

        # create entry boxes
        self.entry_td_min = ttk.Entry(lf_inputs)
        self.entry_td_max = ttk.Entry(lf_inputs)
        self.entry_dps = ttk.Entry(lf_inputs)

        # create sliders and bind to callbacks
        self.scale_td_min = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_td_min.bind("<ButtonRelease-1>", self.callback_s_td_min)
        self.scale_td_min.set(self.td_min.get())
        self.scale_td_max = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_td_max.bind("<ButtonRelease-1>", self.callback_s_td_max)
        self.scale_td_max.set(self.td_max.get())
        self.scale_dps = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_dps.bind("<ButtonRelease-1>", self.callback_s_dps)
        self.scale_dps.set(self.dps.get())

        # put entry boxes in app, bind them to callbacks and initialize their values to the default ones
        self.entry_td_min.grid(row=0, column=2, padx=5, pady=5)
        self.entry_td_min.bind("<Return>", self.callback_e_td_min)
        self.entry_td_min.bind("<FocusOut>", self.callback_e_td_min)
        self.update_entry(self.entry_td_min, self.td_min.get())
        self.entry_td_max.grid(row=1, column=2, padx=5, pady=5)
        self.entry_td_max.bind("<Return>", self.callback_e_td_max)
        self.entry_td_max.bind("<FocusOut>", self.callback_e_td_max)
        self.update_entry(self.entry_td_max, self.td_max.get())
        self.entry_dps.grid(row=2, column=2, padx=5, pady=5)
        self.entry_dps.bind("<Return>", self.callback_e_dps)
        self.entry_dps.bind("<FocusOut>", self.callback_e_dps)
        self.update_entry(self.entry_dps, self.dps.get())

        # put scalers in app
        self.scale_td_min.grid(row=0, column=1, padx=5, pady=5)
        self.scale_td_max.grid(row=1, column=1, padx=5, pady=5)
        self.scale_dps.grid(row=2, column=1, padx=5, pady=5)

        # =DATA FRAME=
        # create random figure
        fig = Figure(figsize=(6, 4), dpi=100)
        t = np.arange(0, 3, .01)
        ax = fig.add_subplot()
        line, = ax.plot(t, 2 * np.sin(2 * np.pi * t))
        ax.set_xlabel("time [s]")
        ax.set_ylabel("f(t)")
        canvas = FigureCanvasTkAgg(fig, master=lf_data)
        canvas.draw()
        # pack_toolbar=False will make it easier to use a layout manager later on.
        toolbar = NavigationToolbar2Tk(canvas, lf_data, pack_toolbar=False)
        toolbar.update()

        # put figure on canvas
        canvas.get_tk_widget().grid(row=0, column=0, padx=5, pady=5)
        toolbar.grid(row=1, column=0, padx=5, pady=5)


def main():
    root = tk.Tk()
    app = Gui(root)
    app.root.mainloop()


if __name__ == "__main__":
    main()
