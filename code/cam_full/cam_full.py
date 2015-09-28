# Gabriel S. Ehrlich
# 28 September 2015
# gabriel.s.ehrlich@gmail.com

"""Pull together measurement widgets into the same program

This module cobbles together the control, acquisition, and data-viewing
widgets defined in cam_full:
- init_w: initialization, temperature control, and closing the camera
    gracefully. On startup of cam_full, this is the only widget
    visible. When the camera is initialized, the rest will start up.
- start_w: setting acquisition parameters and starting/stopping the
    acquisition.
- rms_w: display of the root-mean-square of the probe-only spectra.
- ratio_w: display of the probe-only/pump-probe spectrum ratio.
- probe_only_w and pump_probe_w: display of the respective raw spectra.
"""

import cam_control, acq_control, rms, ratio
from andor.andorcamera import newton, idus
from PyQt4 import QtGui as gui
from plotter import PlotterWidget, AvgPlotter

cam = newton

def start_the_rest(acquiring):
    """Start widgets that need the camera to be initialized to work"""
    global start_w, rms_w, ratio_w, probe_only_w, pump_probe_w
    reload(acq_control)
    reload(rms)
    reload(ratio)

    start_w = acq_control.AcquisitionWidget(cam, acquiring=acquiring)
    start_w.show()

    rms_w = PlotterWidget(rms.RmsPlotter, "RMS/mean counts",
        cam.x, start_w.new_probe_only)
    rms_w.show()
    start_w.startDisplay.connect(rms_w.startAcq)
    start_w.abortDisplay.connect(rms_w.abortAcq)

    ratio_w = PlotterWidget(ratio.RatioPlotter, "Probe-only/pump-probe counts",
        cam.x, start_w.new_probe_only, start_w.new_pump_probe)
    ratio_w.show()
    start_w.startDisplay.connect(ratio_w.startAcq)
    start_w.abortDisplay.connect(ratio_w.abortAcq)

    probe_only_w = PlotterWidget(AvgPlotter, "Probe only",
        cam.x, start_w.new_probe_only)
    probe_only_w.show()
    start_w.startDisplay.connect(probe_only_w.startAcq)
    start_w.abortDisplay.connect(probe_only_w.abortAcq)

    pump_probe_w = PlotterWidget(AvgPlotter, "Pump-probe",
        cam.x, start_w.new_pump_probe)
    pump_probe_w.show()
    start_w.startDisplay.connect(pump_probe_w.startAcq)
    start_w.abortDisplay.connect(pump_probe_w.abortAcq)

def close_the_rest():
    """Remotely close the widgets that are not cam_control"""
    start_w.close()
    rms_w.close()
    ratio_w.close()
    probe_only_w.close()
    pump_probe_w.close()

if __name__ == "__main__":
    app = gui.QApplication([])
    init_w = cam_control.CameraControlWidget(cam)
    init_w.show()
    init_w.cam_initialize_done.connect(start_the_rest)
    init_w.cam_shut_down.connect(close_the_rest)
    app.exec_()