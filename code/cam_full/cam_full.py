import cam_control, acq_control, rms
from andor.andorcamera import newton
from PyQt4 import QtGui as gui, QtCore as core

import time

def start_the_rest():
    global start_w, rms_w
    start_w = acq_control.SimpleController(newton)
    start_w.show()
    rms_w = rms.RmsWidget(newton)
    rms_w.show()
    start_w.new_nmax.connect(rms_w.new_nmax)
    start_w.startAcq.connect(rms_w.startAcq)
    start_w.abortAcq.connect(rms_w.abortAcq)
    rms_w.new_nmax(start_w.spinBox.value())

app = gui.QApplication([])
init_w = cam_control.CameraControlWidget(newton)
init_w.show()
init_w.cam_initialize_done.connect(start_the_rest)
app.exec_()