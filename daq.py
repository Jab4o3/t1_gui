from ctypes import *
from dwfconstants import *
from datetime import datetime
import time
import sys
import matplotlib.pyplot as plt

if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

run_time = 2  # run time (in seconds)
wait_time = 2  # wait time (in seconds)
amplitude = c_double(5)  # signal amplitude (in volts)
daq_sf = 5 * 10 ** 6  # sample frequency of the oscilloscope
pulse_freq = 100000
daq_samples = daq_sf * run_time  # samples to read from the scope
scope_channel = c_int(0)
lia_channel = c_int(0)
hdwf = c_int()

version = create_string_buffer(16)
dwf.FDwfGetVersion(version)
print("DWF Version: " + str(version.value))

# define behavior on close (0 = run, 1 = stop, 2 = shutdown)
dwf.FDwfParamSet(DwfParamOnClose, c_int(0))

# open device and get interface reference
print("Opening first device")
dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

# quit if not found/unavailable
if hdwf.value == hdwfNone.value:
    szerr = create_string_buffer(512)
    dwf.FDwfGetLastErrorMsg(szerr)
    print(str(szerr.value))
    print("Failed to open device")
    quit()

# disable auto config for better performance
dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))

# start reading
status = c_byte()  # recording status
daq_samples_read = 0  # number of read samples
daq_buffer = (c_double * daq_samples)()  # buffer for reading scope data
s_available = c_int()  # avaliable samples
s_lost = c_int()  # lost samples
s_corrupted = c_int()  # corrupted samples
lost = False  # initialize lost flag to false
corrupted = False  # initialize corrupted flag to false

# =OUTPUT=
# enable
dwf.FDwfAnalogOutNodeEnableSet(hdwf, lia_channel, AnalogOutNodeCarrier, c_int(1))
# set function to pulse
dwf.FDwfAnalogOutNodeFunctionSet(hdwf, lia_channel, AnalogOutNodeCarrier, funcPulse)
# set pulse frequency
dwf.FDwfAnalogOutNodeFrequencySet(hdwf, lia_channel, AnalogOutNodeCarrier, c_double(pulse_freq))
# set pulse amplitude to 5V
dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, lia_channel, AnalogOutNodeCarrier, amplitude)
# run continuously
dwf.FDwfAnalogOutConfigure(hdwf, lia_channel, c_int(1))

# =INPUT=
# enable oscilloscope (acquisition) channel
dwf.FDwfAnalogInChannelEnableSet(hdwf, scope_channel, c_int(1))
# set the vertical range of the oscilloscope to 5V
dwf.FDwfAnalogInChannelRangeSet(hdwf, scope_channel, amplitude)
# set the mode of the oscilloscope to record (continuously reading data)
dwf.FDwfAnalogInAcquisitionModeSet(hdwf, acqmodeRecord)
# set the sample frequency of the acquisition to 1MHz
dwf.FDwfAnalogInFrequencySet(hdwf, c_double(daq_sf))
# set the length of the recording to equal that of the run time (or -1 for infinite recording length)
dwf.FDwfAnalogInRecordLengthSet(hdwf, c_double(daq_samples / daq_sf))
# reset trigger timeout and wait for offset to stabilize
dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(0))
time.sleep(wait_time)

# enable
dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))

# read
while daq_samples_read < daq_samples:
    dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(status))
    if daq_samples_read == 0 and (
            status == DwfStateConfig or status == DwfStatePrefill or status == DwfStateArmed):
        # acquisition hasn't started yet
        continue

    # retrieve information about data loss and corruption
    dwf.FDwfAnalogInStatusRecord(hdwf, byref(s_available), byref(s_lost), byref(s_corrupted))

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
    dwf.FDwfAnalogInStatusData(hdwf, scope_channel,
                               byref(daq_buffer, sizeof(c_double) * daq_samples_read),
                               s_available)
    daq_samples_read += s_available.value

    print(f"{daq_samples_read} of {daq_samples}")

# throw exception if data is lost
if lost or corrupted:
    print("AD2", "Lost data", f"Data lost or corrupted")
    # raise ValueError(
    #     f"Data lost or corrupted due to high sample frequency ({daq_sf / 1000} kHz)")

# write data to csv file
file_name = f"./logs/data_point_" + datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + ".csv"
f = open(file_name, "a")
for j in daq_buffer:
    f.write("%s\n" % j)
f.close()

plt.plot(daq_buffer)
plt.xlabel("Time")
plt.xlim(0, 5 * daq_sf / pulse_freq)
plt.ylabel("Voltage (V)")

plt.show()
