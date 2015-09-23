from PyQt4 import QtCore as core, QtGui as gui, uic
import numpy as np
import warnings

ui_filename = "acq_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SimpleControllerWidget(gui.QWidget, Ui_Widget):
    getBackground = core.pyqtSignal()
    startAcq = core.pyqtSignal(np.ndarray)
    startDisplay = core.pyqtSignal()
    abortAcq = core.pyqtSignal()
    abortDisplay = core.pyqtSignal()

    new_pump_probe = core.pyqtSignal(np.ndarray, np.ndarray)
    new_probe_only = core.pyqtSignal(np.ndarray, np.ndarray)

    def __init__(self, cam):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.controller = SimpleController(cam)
        self.startButton.clicked.connect(
            self.controller.on_startButton_clicked)
        self.abortButton.clicked.connect(
            self.controller.on_abortButton_clicked)
        self.controller.startAcq.connect(self.startAcq)
        self.controller.startDisplay.connect(self.startDisplay)
        self.controller.abortAcq.connect(self.abortAcq)
        self.controller.abortDisplay.connect(self.abortDisplay)
        self.controller.new_pump_probe.connect(self.new_pump_probe)
        self.controller.new_probe_only.connect(self.new_probe_only)

class SimpleController(core.QObject):
    getBackground = core.pyqtSignal()
    startAcq = core.pyqtSignal(np.ndarray)
    startDisplay = core.pyqtSignal()
    abortAcq = core.pyqtSignal()
    abortDisplay = core.pyqtSignal()

    new_pump_probe = core.pyqtSignal(np.ndarray, np.ndarray)
    new_probe_only = core.pyqtSignal(np.ndarray, np.ndarray)

    def __init__(self, cam):
        core.QObject.__init__(self)

        # cam already inited and in another thread
        self.cam = cam
        self.getBackground.connect(self.cam.get_background)
        self.startAcq.connect(self.cam.scan_until_abort)
        self.abortAcq.connect(self.cam.abort)

        # Create event loop for self so that incoming signals are queued
        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)

    def send_new_images(self, n_new):
        if n_new == 1:
            if self.next_data_has_pump:
                self.new_pump_probe.emit(self.wavelen_arr,
                    self.pump_probe_data - self.background)
                self.next_data_has_pump = False
            else:
                self.new_probe_only.emit(self.wavelen_arr,
                    self.probe_only_data - self.background)
                self.next_data_has_pump = True
        else: # n_new == 2
            self.new_probe_only.emit(self.wavelen_arr,
                self.probe_only_data - self.background)
            self.new_pump_probe.emit(self.wavelen_arr,
                self.pump_probe_data - self.background)

    @core.pyqtSlot()
    def on_startButton_clicked(self):
        self.cam.acquisition_done.connect(self.continue_with_exposure)
        self.getBackground.emit()

        #self.continue_with_exposure(self.cam.get_new_array(n_images=1))

    def continue_with_exposure(self, background):
        self.cam.acquisition_done.disconnect(self.continue_with_exposure)
        self.background = background[0] # shape: (1, 1024) -> (1024)

        self.data_pair = self.cam.get_new_array(n_images=2)
        self.pump_probe_data = self.data_pair[0]
        self.probe_only_data = self.data_pair[1]
        self.next_data_has_pump = True

        self.cam.new_images.connect(self.send_new_images)
        self.wavelen_arr = self.cam.get_wavelen_array()

        self.startAcq.emit(self.data_pair) # get 2 images at a time

        # Tell listeners to start displaying data too
        self.startDisplay.emit()

    @core.pyqtSlot()
    def on_abortButton_clicked(self):
        self.cam.new_images.disconnect(self.send_new_images)
        self.abortAcq.emit()
        self.abortDisplay.emit()

        del self.background
        del self.data_pair, self.pump_probe_data, self.probe_only_data
        del self.next_data_has_pump
        del self.wavelen_arr