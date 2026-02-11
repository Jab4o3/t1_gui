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
        self.td_min = tk.DoubleVar(root, value=0)
        self.td_max = tk.DoubleVar(root, value=0)
        self.dps = tk.DoubleVar(root, value=0)
        # TODO: Add tracking to variables

        self.populate()

    """
    Set value of Tkinter entry
    """

    def update_entry(self, e, value):
        e.delete(0, tk.END)
        e.insert(0, value)
        return

    """
       Set value of Tkinter entry
       """

    def update_entry_from_scroller(self, e, s, value):
        e.delete(0, tk.END)
        e.insert(0, value)
        return

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

        # create scalers
        scaler_td_min = tk.Scale(lf_inputs, variable=self.td_min, from_=1, to=100, orient=tk.HORIZONTAL)
        scaler_td_max = tk.Scale(lf_inputs, variable=self.td_max, from_=1, to=100, orient=tk.HORIZONTAL)
        scaler_dps = tk.Scale(lf_inputs, variable=self.dps, from_=1, to=100, orient=tk.HORIZONTAL)

        # put scalers in app
        scaler_td_min.grid(row=0, column=1, padx=5, pady=5)
        scaler_td_max.grid(row=1, column=1, padx=5, pady=5)
        scaler_dps.grid(row=2, column=1, padx=5, pady=5)

        # create entry boxes
        entry_td_min = ttk.Entry(lf_inputs)
        entry_td_max = ttk.Entry(lf_inputs)
        entry_dps = ttk.Entry(lf_inputs)

        # put entry boxes in app and initialize their values to the default ones
        entry_td_min.grid(row=0, column=2, padx=5, pady=5)
        entry_td_max.grid(row=1, column=2, padx=5, pady=5)
        entry_dps.grid(row=2, column=2, padx=5, pady=5)
        self.update_entry(entry_td_min, self.td_min)
        self.update_entry(entry_td_max, self.td_max)
        self.update_entry(entry_dps, self.td_max)

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
