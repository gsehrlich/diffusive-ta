from PyQt4 import QtCore as core, QtGui as gui, uic
import numpy as np

ui_filename = "acq_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SimpleController(gui.QWidget, Ui_Widget):
    new_nmax = core.pyqtSignal(int)
    startAcq = core.pyqtSignal(np.ndarray)
    abortAcq = core.pyqtSignal()

    def __init__(self, cam):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.cam = cam
        self.data = cam.get_new_array(n_images=1)

        # cam already inited and in another thread
        self.startAcq.connect(self.cam.scan_until_abort)
        self.abortAcq.connect(self.cam.abort)

    def on_spinBox_valueChanged(self):
        self.new_nmax.emit(self.spinBox.value())

    def on_startButton_clicked(self):
        self.startAcq.emit(self.data)

    def on_abortButton_clicked(self):
        self.abortAcq.emit()