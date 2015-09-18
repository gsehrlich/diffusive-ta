import cam_control, acq_control, rms
from andor.andorcamera import newton
from PyQt4 import QtGui as gui, QtCore as core

import time

def start_the_rest():
    global start_w, rms_w
    reload(acq_control)
    reload(rms)
    start_w = acq_control.SimpleController(newton)
    start_w.show()
    rms_w = rms.RmsWidget(newton.x, start_w.new_probe_only)
    rms_w.show()
    start_w.new_nmax.connect(rms_w.new_nmax)
    start_w.startDisplay.connect(rms_w.startAcq)
    start_w.abortDisplay.connect(rms_w.abortAcq)
    rms_w.new_nmax(start_w.spinBox.value())

def close_the_rest():
    start_w.close()
    rms_w.close()

app = gui.QApplication([])
init_w = cam_control.CameraControlWidget(newton)
init_w.show()
init_w.cam_initialize_done.connect(start_the_rest)
init_w.cam_shut_down.connect(close_the_rest)
app.exec_()