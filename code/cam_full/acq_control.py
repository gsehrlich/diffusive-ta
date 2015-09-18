from PyQt4 import QtCore as core, QtGui as gui, uic
import numpy as np
import warnings

ui_filename = "acq_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SimpleController(gui.QWidget, Ui_Widget):
    new_nmax = core.pyqtSignal(int)
    startAcq = core.pyqtSignal(np.ndarray)
    startDisplay = core.pyqtSignal()
    abortAcq = core.pyqtSignal()
    abortDisplay = core.pyqtSignal()

    new_pump_probe = core.pyqtSignal(np.ndarray)
    new_probe_only = core.pyqtSignal(np.ndarray)

    def __init__(self, cam):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.cam = cam
        self.data_pair = self.cam.get_new_array(n_images=2)
        self.pump_probe_data = self.data_pair[0]
        self.probe_only_data = self.data_pair[1]
        self.next_data_has_pump = True

        # cam already inited and in another thread
        self.startAcq.connect(self.cam.scan_until_abort)
        self.abortAcq.connect(self.cam.abort)
        self.cam.new_images.connect(self.send_new_images)

    def send_new_images(self, n_new):
        if n_new == 1:
            if self.next_data_has_pump:
                self.new_pump_probe.emit(self.pump_probe_data)
                self.next_data_has_pump = False
            else:
                self.new_probe_only.emit(self.probe_only_data)
                self.next_data_has_pump = True
        else: # n_new == 2
            self.new_pump_probe.emit(self.pump_probe_data)
            self.new_probe_only.emit(self.probe_only_data)

    def on_spinBox_valueChanged(self):
        self.new_nmax.emit(self.spinBox.value())

    @core.pyqtSlot()
    def on_startButton_clicked(self):
        self.startAcq.emit(self.data_pair) # get 2 images at a time

        # Tell listeners to start displaying data too
        self.startDisplay.emit()

    @core.pyqtSlot()
    def on_abortButton_clicked(self):
        self.abortAcq.emit()
        self.abortDisplay.emit()