import time
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
import threading

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
        self.p_width = tk.DoubleVar(root, value=1)
        self.scale_p_width = None
        self.entry_p_width = None
        # maximum dark time
        self.td_max = tk.DoubleVar(root, value=1)
        self.scale_td_max = None
        self.entry_td_max = None
        # number of data points
        self.dps = tk.IntVar(root, value=10)
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
        self.scope_channel = c_int(0)  # oscilloscope channel 1
        self.find_device()  # look for an AD2 on startup

        # =T1 measurements=
        self.pattern_size = 4096  # fixed pattern buffer size
        self.sequences = []  # list of T1 sequences
        self.t1_thread = None  # thread that does T1 IO
        self.file_name = None  # name of the last plot csv file

    """
    Generate a pseudo-logarithmic integer space for generating dark times with different sample sizes
    """

    def gen_log_space(self, td_min, td_max, n):
        result = [td_min]
        # return 1 if bad n
        if n <= 1:
            return result

        for i in range(1, n):
            td_curr = td_min + round(10 ** (i * log10(td_max) / (n - 1)))
            # exits prematurely if min and max are too close
            if td_curr >= td_max:
                result.append(td_max)
                return result

            # check if dark time is repeating last value and increment it if yes
            if td_curr - result[-1] >= 1:
                result.append(td_curr)
            else:
                result.append(result[-1] + 1)
        return result

    """
    Connect to AD2 or show that it is not connected
    """

    def find_device(self):
        # TODO: add disconnect handler
        # version required for operation
        version = create_string_buffer(16)
        dwf.FDwfGetVersion(version)
        print("DWF Version: " + str(version.value))

        # define behavior on close (0 = run, 1 = stop, 2 = shutdown)
        dwf.FDwfParamSet(DwfParamOnClose, c_int(0))

        # open device and get interface reference
        ret_code = dwf.FDwfDeviceOpen(c_int(-1), byref(self.hdwf))

        if ret_code:
            self.log_message("AD2", "Connection", f"Connected to AD2, DWF Version {str(version.value)}")
            self.status.set("Connected")
        else:
            szerr = create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(szerr)
            self.log_message("AD2", "Connection", szerr.value)

        # disable auto config for better performance
        dwf.FDwfDeviceAutoConfigureSet(self.hdwf, c_int(0))
        return ret_code

    """
    Generate sequences for pulsing
    """

    def t1_generate_sequences(self):
        # constants
        pw = 5  # pulse width (in buffer slots)
        min_td = 1  # minimum dark time (in buffer slots)
        min_td_time = (10 ** -6) * min_td * self.p_width.get() / pw  # get minimum dark time (in seconds)
        t_pattern = min_td_time * self.pattern_size  # set period of the whole pattern
        f_pattern = 1 / t_pattern  # set frequency of the whole pattern
        # fixed minimum dark time to pulse width ratio
        max_td = round((10 ** -3) * self.td_max.get() / min_td_time)
        if max_td < min_td:
            self.log_message("T1", "Gen error", "Maximum dark time was calculated to be smaller than the minimum")
            raise ValueError(f"Maximum dark time (td = {max_td}) cannot be smaller than the minimum (td = {min_td})")
        if max_td > 2000:
            self.log_message("T1", "Gen error",
                             f"Maximum dark time (td = {max_td}) too big for buffer; should be less than 2000 ")
            raise ValueError(f"Maximum dark time (td = {max_td}) too big for buffer")
        all_tds = self.gen_log_space(td_min=min_td, td_max=max_td, n=self.dps.get())  # pseudo-logspace of dark times

        # make pattern
        for curr_td in all_tds:
            pattern = (c_double * self.pattern_size)(0)  # initialize C-style zero array
            for i in range(0, pw):
                pattern[i] = 1  # cancellation pulse
                pattern[i + int(self.pattern_size / 2)] = 1  # initialization pulse
                pattern[i + pw + curr_td + int(self.pattern_size / 2)] = 1  # readout pulse
            self.sequences.append(pattern)
        return f_pattern

    """
    Command for running T1 tests
    """

    def command_run_t1(self):
        # exit if no device is found
        if not self.hdwf:
            self.log_message("T1", "Connection", "Connect a device to start tests")
            return
        f_pattern = self.t1_generate_sequences()  # generate all sequences

        run_time = 10  # run time (in seconds)
        wait_time = 10  # wait time (in seconds)
        amplitude = c_double(5)  # signal amplitude (in volts)
        daq_sf = 10 ** 6  # sample frequency of the oscilloscope
        daq_samples = daq_sf * run_time  # samples to read from the scope
        self.log_message("T1", "Test started", "Values generated successfully")
        for i in range(len(self.sequences)):
            pattern = self.sequences[i]
            # =LASER CHANNEL CONFIG=
            # enable
            dwf.FDwfAnalogOutNodeEnableSet(self.hdwf, self.laser_channel, AnalogOutNodeCarrier, c_int(1))

            # set function to custom
            dwf.FDwfAnalogOutNodeFunctionSet(self.hdwf, self.laser_channel, AnalogOutNodeCarrier, funcCustom)

            # set pattern of custom function
            dwf.FDwfAnalogOutNodeDataSet(self.hdwf, self.laser_channel, AnalogOutNodeCarrier, pattern,
                                         c_int(self.pattern_size))

            # set frequency of the whole pattern
            dwf.FDwfAnalogOutNodeFrequencySet(self.hdwf, self.laser_channel, AnalogOutNodeCarrier, c_double(f_pattern))

            # set amplitude of the whole pattern to 5V
            dwf.FDwfAnalogOutNodeAmplitudeSet(self.hdwf, self.laser_channel, AnalogOutNodeCarrier, amplitude)

            # set the run and wait time (in seconds)
            dwf.FDwfAnalogOutRunSet(self.hdwf, self.laser_channel, c_double(run_time))
            dwf.FDwfAnalogOutWaitSet(self.hdwf, self.laser_channel, c_double(wait_time))

            # =LIA CHANNEL CONFIG=
            # enable
            dwf.FDwfAnalogOutNodeEnableSet(self.hdwf, self.lia_channel, AnalogOutNodeCarrier, c_int(1))

            # set function to pulse
            dwf.FDwfAnalogOutNodeFunctionSet(self.hdwf, self.lia_channel, AnalogOutNodeCarrier, funcPulse)

            # set pulse frequency
            dwf.FDwfAnalogOutNodeFrequencySet(self.hdwf, self.lia_channel, AnalogOutNodeCarrier, c_double(f_pattern))

            # set pulse amplitude to 5V
            dwf.FDwfAnalogOutNodeAmplitudeSet(self.hdwf, self.lia_channel, AnalogOutNodeCarrier, amplitude)

            # set the run and wait time (in seconds)
            dwf.FDwfAnalogOutRunSet(self.hdwf, self.lia_channel, c_double(run_time / f_pattern))
            dwf.FDwfAnalogOutWaitSet(self.hdwf, self.lia_channel, c_double(wait_time / f_pattern))

            # =OSCILLOSCOPE (DAQ) CHANNEL CONFIG=
            # enable oscilloscope (acquisition) channel
            dwf.FDwfAnalogInChannelEnableSet(self.hdwf, self.scope_channel, c_int(1))

            # set the vertical range of the oscilloscope to 5V
            dwf.FDwfAnalogInChannelRangeSet(self.hdwf, self.scope_channel, amplitude)

            # set the mode of the oscilloscope to record (continuously reading data)
            dwf.FDwfAnalogInAcquisitionModeSet(self.hdwf, acqmodeRecord)

            # set the sample frequency of the acquisition to 1MHz
            dwf.FDwfAnalogInFrequencySet(self.hdwf, c_double(daq_sf))

            # set the length of the recording to equal that of the run time (or -1 for infinite recording length)
            dwf.FDwfAnalogInRecordLengthSet(self.hdwf, c_double(daq_samples))

            # reset trigger timeout and wait for offset to stabilize
            dwf.FDwfAnalogInConfigure(self.hdwf, c_int(1), c_int(0))
            time.sleep(2)

            self.log_message("T1", "Sequence started", f"Starting data point number {i}")
            # =OUTPUT/DAQ=
            # start outputting
            dwf.FDwfAnalogOutConfigure(self.hdwf, self.laser_channel, c_int(1))
            dwf.FDwfAnalogOutConfigure(self.hdwf, self.lia_channel, c_int(1))

            # start reading
            status = c_byte()  # recording status
            daq_samples_read = 0  # number of read samples
            daq_buffer = (c_double * daq_samples)()  # buffer for reading scope data
            s_available = c_int()  # avaliable samples
            s_lost = c_int()  # lost samples
            s_corrupted = c_int()  # corrupted samples
            lost = False  # initialize lost flag to false
            corrupted = False  # initialize corrupted flag to false

            # enable
            dwf.FDwfAnalogInConfigure(self.hdwf, c_int(0), c_int(1))

            # read
            while daq_samples_read < daq_samples:
                dwf.FDwfAnalogInStatus(self.hdwf, c_int(1), byref(status))
                if daq_samples_read == 0 and (
                        status == DwfStateConfig or status == DwfStatePrefill or status == DwfStateArmed):
                    # acquisition hasn't started yet
                    continue

                # retrieve information about data loss and corruption
                dwf.FDwfAnalogInStatusRecord(self.hdwf, byref(s_available), byref(s_lost), byref(s_corrupted))

                daq_samples_read += s_lost.value

                # update lost and corrupted flags
                if s_lost.value:
                    lost = True
                if s_corrupted.value:
                    corrupted = True

                if s_available.value == 0:
                    break
                # truncate data if too big for buffer
                if daq_samples_read + s_available.value > daq_samples:
                    s_available = c_int(daq_samples - daq_samples_read)

                    # get scope channel data and copy it to the buffer
                dwf.FDwfAnalogInStatusData(self.hdwf, self.scope_channel,
                                           byref(daq_buffer, sizeof(c_double) * daq_samples_read),
                                           s_available)
                daq_samples_read += s_available.value

            # throw exception if data is lost
            if lost or corrupted:
                self.log_message("AD2", "Lost data", f"Data lost or corrupted (data point {i})")
                raise ValueError(
                    f"Data lost or corrupted (data point {i}) due to high sample frequency ({daq_sf / 1000} kHz)")

            # write data to csv file
            self.file_name = f"data_point_{i}" + datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + ".csv"
            f = open(self.file_name, "w")
            for j in daq_buffer:
                f.write("%s\n" % j)
            f.close()

            # wait for this sequence to complete before moving on
            time.sleep(run_time + wait_time)

        # reset and close device
        dwf.FDwfAnalogOutReset(self.hdwf, self.laser_channel)
        dwf.FDwfAnalogOutReset(self.hdwf, self.lia_channel)
        dwf.FDwfDeviceCloseAll()

    """
    Threaded version of the T1 command
    """

    def thread_command_run_t1(self):
        # only run if T1 is not currently running
        if self.t1_thread is None or not self.t1_thread.is_alive():
            self.t1_thread = threading.Thread(target=self.command_run_t1)
            self.t1_thread.start()
        else:
            self.log_message("T1", "Test not started", "Wait for the current test to finish before starting a new one")

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

    def callback_s_p_width(self, event):
        if self.scale_p_width != self.p_width.get():
            self.p_width.set(self.scale_p_width.get())
            self.update_entry(self.entry_p_width, self.p_width.get())

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

    def callback_e_p_width(self, event):
        if float(self.entry_p_width.get()) != self.p_width.get():
            self.p_width.set(self.entry_p_width.get())
            self.scale_p_width.set(self.p_width.get())

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

    # def command_find_device(self):


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

        # create scan button
        button_scan = ttk.Button(lf_devices, text="Scan", command=self.find_device)

        # put scan button in app
        button_scan.grid(row=0, column=2, rowspan=2, sticky="W", padx=5, pady=5)

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
        self.tree_running_log.column("Value", minwidth=10, width=300)

        # put tree in app
        self.tree_running_log.grid(row=0, column=0, sticky=("N", "W", "E", "S"), padx=5, pady=5)

        # log first status message
        self.log_message("GUI", "Startup", "GUI created")

        # =INPUT FRAME=
        # create labels
        label_p_width = ttk.Label(lf_inputs, text="Pulse width (in us)")
        label_td_max = ttk.Label(lf_inputs, text="Maximum dark time (in ms)")
        label_dps = ttk.Label(lf_inputs, text="Number of data points")

        # put labels in app
        label_p_width.grid(row=0, column=0, sticky="W", padx=5, pady=5)
        label_td_max.grid(row=1, column=0, sticky="W", padx=5, pady=5)
        label_dps.grid(row=2, column=0, sticky="W", padx=5, pady=5)

        # create entry boxes
        self.entry_p_width = ttk.Entry(lf_inputs)
        self.entry_td_max = ttk.Entry(lf_inputs)
        self.entry_dps = ttk.Entry(lf_inputs)

        # create sliders and bind to callbacks
        self.scale_p_width = tk.Scale(lf_inputs, from_=0.1, to=10, resolution=0.01, orient=tk.HORIZONTAL)
        self.scale_p_width.bind("<ButtonRelease-1>", self.callback_s_p_width)
        self.scale_p_width.set(self.p_width.get())
        self.scale_td_max = tk.Scale(lf_inputs, from_=0.01, to=5, resolution=0.01, orient=tk.HORIZONTAL)
        self.scale_td_max.bind("<ButtonRelease-1>", self.callback_s_td_max)
        self.scale_td_max.set(self.td_max.get())
        self.scale_dps = tk.Scale(lf_inputs, from_=5, to=50, orient=tk.HORIZONTAL)
        self.scale_dps.bind("<ButtonRelease-1>", self.callback_s_dps)
        self.scale_dps.set(self.dps.get())

        # put entry boxes in app, bind them to callbacks and initialize their values to the default ones
        self.entry_p_width.grid(row=0, column=2, padx=5, pady=5)
        self.entry_p_width.bind("<Return>", self.callback_e_p_width)
        self.entry_p_width.bind("<FocusOut>", self.callback_e_p_width)
        self.update_entry(self.entry_p_width, self.p_width.get())
        self.entry_td_max.grid(row=1, column=2, padx=5, pady=5)
        self.entry_td_max.bind("<Return>", self.callback_e_td_max)
        self.entry_td_max.bind("<FocusOut>", self.callback_e_td_max)
        self.update_entry(self.entry_td_max, self.td_max.get())
        self.entry_dps.grid(row=2, column=2, padx=5, pady=5)
        self.entry_dps.bind("<Return>", self.callback_e_dps)
        self.entry_dps.bind("<FocusOut>", self.callback_e_dps)
        self.update_entry(self.entry_dps, self.dps.get())

        # put sliders in app
        self.scale_p_width.grid(row=0, column=1, padx=5, pady=5)
        self.scale_td_max.grid(row=1, column=1, padx=5, pady=5)
        self.scale_dps.grid(row=2, column=1, padx=5, pady=5)

        # create run button
        button_run = ttk.Button(lf_inputs, text="Run", command=self.thread_command_run_t1)

        # put run button in app
        button_run.grid(row=0, column=3, rowspan=3, padx=5, pady=5)

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
