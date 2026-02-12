import tkinter as tk
from tkinter import ttk
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure
import numpy as np

"""
Main GUI class
"""


class Gui:
    def __init__(self, root, title="T1 measurements"):
        self.root = root
        self.root.title(title)
        self.root.resizable(height=False, width=False)  # make window non-resizable
        # associate entries and scales with object for callback references
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

        self.populate()

    """
    Set value of Tkinter entry
    """

    def update_entry(self, e, value):
        e.delete(0, tk.END)
        e.insert(0, value)
        return

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
        lf_inputs = ttk.Labelframe(self.root, text="T1 parameters")
        lf_data = ttk.Labelframe(self.root, text="Test data")

        # put frames in app
        lf_devices.grid(row=0, column=0, padx=5, pady=5, sticky=("N", "W", "E", "S"))
        lf_inputs.grid(row=1, column=0, padx=5, pady=5, sticky=("N", "W", "E", "S"))
        lf_data.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky=("N", "W", "E", "S"))

        # =DEVICE FRAME=
        # create labels
        label_dev = ttk.Label(lf_devices, text="Device")

        # put labels in app
        label_dev.grid(row=0, column=0, sticky="W", padx=5, pady=5)

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

        # create scalers and bind to callbacks
        self.scale_td_min = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_td_min.bind("<ButtonRelease-1>", self.callback_s_td_min)
        self.scale_td_max = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_td_max.bind("<ButtonRelease-1>", self.callback_s_td_max)
        self.scale_dps = tk.Scale(lf_inputs, from_=1, to=100, orient=tk.HORIZONTAL)
        self.scale_dps.bind("<ButtonRelease-1>", self.callback_s_dps)

        # put entry boxes in app and initialize their values to the default ones
        self.entry_td_min.grid(row=0, column=2, padx=5, pady=5)
        self.entry_td_min.bind("<Return>", self.callback_e_td_min)
        self.entry_td_max.grid(row=1, column=2, padx=5, pady=5)
        self.entry_td_max.bind("<Return>", self.callback_e_td_max)
        self.entry_dps.grid(row=2, column=2, padx=5, pady=5)
        self.entry_dps.bind("<Return>", self.callback_e_dps)

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

        canvas.get_tk_widget().grid(row=0, column=0, padx=5, pady=5)
        toolbar.grid(row=1, column=0, padx=5, pady=5)


def main():
    root = tk.Tk()
    app = Gui(root)
    app.root.mainloop()


if __name__ == "__main__":
    main()