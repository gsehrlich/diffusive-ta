import cam_control, acq_control, rms, ratio
from andor.andorcamera import newton, idus
from PyQt4 import QtGui as gui, QtCore as core
from plotter import PlotterWidget, AvgPlotter

cam = newton

def start_the_rest():
    global start_w, rms_w, ratio_w, probe_only_w, pump_probe_w
    reload(acq_control)
    reload(rms)
    reload(ratio)
    start_w = acq_control.SimpleControllerWidget(cam)
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
    start_w.close()
    rms_w.close()
    ratio_w.close()
    probe_only_w.close()
    pump_probe_w.close()

app = gui.QApplication([])
init_w = cam_control.CameraControlWidget(cam)
init_w.show()
init_w.cam_initialize_done.connect(start_the_rest)
init_w.cam_shut_down.connect(close_the_rest)
app.exec_()