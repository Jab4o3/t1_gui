"""
Pulse generation script for the Analog Discovery 2 using the Digilent SDK
"""

from ctypes import *
from dwfconstants import *
import sys

if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

f_pattern = 100
pattern_size = 4096
td = 10  # dark time (in buffer slots)
pw = 50  # pulse width (in buffer slots)
print("+++++++++++++++++++++++++++")
print("Dark time: " + str((10 ** 6) * td / (f_pattern * pattern_size)) + " us")
print("Pulse width: " + str((10 ** 6) * pw / (f_pattern * pattern_size)) + " us")
print("+++++++++++++++++++++++++++")
hdwf = c_int()
# pattern = (c_double * pattern_size)()
pattern = (c_double * pattern_size)(0)  # initialize C-style zero array
print(pattern)
channel = c_int(0)  # wavegen channel 1

# make pattern
for i in range(0, pw):
    pattern[i] = 1  # cancellation pulse
    pattern[int(i + (pattern_size / 2))] = 1  # initialization pulse
    pattern[int(i + pw + td + (pattern_size / 2))] = 1  # readout pulse

# # print pattern
# for i in range(0, len(pattern)):
#     print(pattern[i])

# for i in range(0, len(pattern)):
#     pattern[i] = 1.0 * i / pattern_size

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
    print(szerr.value)
    print("Failed to open device")
    quit()

# disable auto config for better performance
dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))
#
# pf_pattern = c_double()
# dwf.FDwfDigitalOutInternalClockInfo(hdwf, byref(pf_pattern))
# print("Clock frequency: " + pf_pattern.value.__str__())

print("Generating custom waveform...")
print("Enable: " + dwf.FDwfAnalogOutNodeEnableSet(hdwf, channel, AnalogOutNodeCarrier, c_int(1)).__str__())
print("Set function to custom: " + dwf.FDwfAnalogOutNodeFunctionSet(hdwf, channel, AnalogOutNodeCarrier,
                                                                    funcCustom).__str__())
print("Set data pattern: " + dwf.FDwfAnalogOutNodeDataSet(hdwf, channel, AnalogOutNodeCarrier, pattern,
                                                          c_int(pattern_size)).__str__())
print("Set frequency: " + dwf.FDwfAnalogOutNodeFrequencySet(hdwf, channel, AnalogOutNodeCarrier,
                                                            c_double(f_pattern)).__str__())
print(
    "Set amplitude: " + dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, channel, AnalogOutNodeCarrier, c_double(5.0)).__str__())

print("Run period set: " + dwf.FDwfAnalogOutRunSet(hdwf, channel,
                                                   c_double(10000.0 / f_pattern)).__str__())  # run for 2 periods
# print("Wait period set: " + dwf.FDwfAnalogOutWaitSet(hdwf, channel, c_double(1000.0 / f_pattern)).__str__())  # wait one pulse time
print("Repetitions set: " + dwf.FDwfAnalogOutRepeatSet(hdwf, channel, c_int(3)).__str__())  # repeat 3 times

print("Output config: " + dwf.FDwfAnalogOutConfigure(hdwf, channel, c_int(1)).__str__())
print("Generating waveform...")

dwf.FDwfAnalogOutReset(hdwf, channel)
dwf.FDwfDeviceCloseAll()
