from __future__ import print_function
from PyQt4 import QtCore as core, QtGui as gui, uic
import numpy as np
import warnings
import atexit

ui_filename = "acq_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class AcquisitionWidget(gui.QWidget, Ui_Widget):
    getBackground = core.pyqtSignal()
    start = core.pyqtSignal()
    abort = core.pyqtSignal()

    acquisition_settings = core.pyqtSignal(str, str, float, float, int, float,
        int, str, str, bool)

    new_pump_probe = core.pyqtSignal(np.ndarray, np.ndarray)
    new_probe_only = core.pyqtSignal(np.ndarray, np.ndarray)

    flipPumpOnlyPumpProbe = core.pyqtSignal()

    def __init__(self, cam, acquiring=False):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Set up stationary parts of the GUI. setupUi crashes on QComboBoxes,
        # so add them manually here
        self.cam = cam
        self.nameLabel.setText(self.cam.name)
        self.addComboBoxToFormLayout(0, "acquisitionModeComboBox",
            ["Scan until abort"], enabled=False)
        self.addComboBoxToFormLayout(1, "readModeComboBox",
            ["Full vertical binning"], enabled=False)
        self.addComboBoxToFormLayout(7, "triggerSourceComboBox",
            ["Internal", "External"])
        self.addComboBoxToFormLayout(8, "keepCleanModeComboBox",
            ["Wait", "Trigger abort"], enabled=False)
        # ONLY AVAILABLE ON NEWTON IN FVB EXTERNAL TRIGGER MODE
        if self.cam.name == "newton":
            self.keepCleanModeComboBox.addItem("Disable")

        # Allow only sensible inputs for lineedits
        self.exposureTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.accumTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.kinTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))

        # Connect GUI signals that aren't automatically connected
        self.triggerSourceComboBox.currentIndexChanged.connect(
            self.on_triggerSourceComboBox_currentIndexChanged)
        self.keepCleanModeComboBox.currentIndexChanged.connect(
            self.on_keepCleanModeComboBox_currentIndexChanged)

        # For making read-only during acquisition
        self.enabled_input_widgets = (
            self.label_4,
            self.exposureTimeLineEdit,
            self.label_9,
            self.triggerSourceComboBox,
            self.label_10,
            self.keepCleanModeComboBox,
            self.takeBackgroundCheckBox
            )

        self.controller = Acquirer(self.cam)
        self.acquisition_settings.connect(
            self.controller.prep_acquisition)
        self.start.connect(self.controller.on_start)
        self.flipPumpOnlyPumpProbe.connect(self.controller.on_flip)
        self.abort.connect(self.controller.on_abort)
        self.controller.acquisition_timings.connect(self.update_timing)
        self.controller.abortion_done.connect(self.finish_abortion)

        # Allow other objects to connect these signals without referencing
        # controller directly
        self.startAcq = self.controller.startAcq
        self.startDisplay = self.controller.startDisplay
        self.abortAcq = self.controller.abortAcq
        self.abortDisplay = self.controller.abortDisplay
        self.new_pump_probe = self.controller.new_pump_probe
        self.new_probe_only = self.controller.new_probe_only

        # Fill in real exposure times
        self.send_acquisition_settings()

        # If a bad shutdown somehow left the camera acquiring, allow the user
        # to abort it
        if acquiring:
            self.set_acquisition_gui()

    def addComboBoxToFormLayout(self, row, name, menu_items, enabled=True):
        if hasattr(self, name):
            raise ValueError("can't add combo box named %r: name exists" % name)
        setattr(self, name, gui.QComboBox())
        self.formLayout.setWidget(row, 1, getattr(self, name))
        getattr(self, name).setEnabled(enabled) # TODO
        getattr(self, name).addItems(menu_items)

    def send_acquisition_settings(self):
        self.acquisition_settings.emit(
            self.acquisitionModeComboBox.currentText(),
            self.readModeComboBox.currentText(),
            float(self.exposureTimeLineEdit.text()),
            float(self.accumTimeLineEdit.text()),
            self.nAccumsSpinBox.value(),
            float(self.kinTimeLineEdit.text()),
            self.nKineticsSpinBox.value(),
            self.triggerSourceComboBox.currentText(),
            self.keepCleanModeComboBox.currentText(),
            bool(self.takeBackgroundCheckBox.isChecked())
            )

    def update_timing(self, exp, accum, kin, min_trigger_period,
            enable_keepCleanModeComboBox):
        self.exposureTimeLineEdit.setText("{:.2f}".format(exp * 1000))
        self.accumTimeLineEdit.setText("{:.2f}".format(accum * 1000))
        self.kinTimeLineEdit.setText("{:.2f}".format(kin * 1000))

        # Pass -1. for min_trigger_period if it doesn't apply
        if min_trigger_period == -1.:
            self.minTriggerPeriodLabel.setText("N/A")
            self.minTriggerPeriodLabel.setEnabled(False)
            self.label_11.setEnabled(False)
        else:
            self.minTriggerPeriodLabel.setText("{:.2f} ms".format(
                min_trigger_period*1000))
            self.minTriggerPeriodLabel.setEnabled(True)
            self.label_11.setEnabled(True)

        self.label_10.setEnabled(enable_keepCleanModeComboBox)
        self.keepCleanModeComboBox.setEnabled(enable_keepCleanModeComboBox)

    @core.pyqtSlot()
    def on_startButton_clicked(self):
        self.set_acquisition_gui()
        self.start.emit()

    def set_acquisition_gui(self):
        self.startButton.setEnabled(False)
        for widget in self.enabled_input_widgets:
            widget.setEnabled(False)
        self.abortButton.setEnabled(True)
        self.flipPumpOnlyPumpProbeButton.setEnabled(True)

    @core.pyqtSlot()
    def on_abortButton_clicked(self):
        self.abortButton.setEnabled(False)
        self.flipPumpOnlyPumpProbeButton.setEnabled(False)
        self.abort.emit()

    def finish_abortion(self):
        for widget in self.enabled_input_widgets:
            widget.setEnabled(True)
        self.startButton.setEnabled(True)

    @core.pyqtSlot()
    def on_exposureTimeLineEdit_editingFinished(self):
        self.send_acquisition_settings()

    @core.pyqtSlot(str)
    def on_triggerSourceComboBox_currentIndexChanged(self, mode):
        self.send_acquisition_settings()

    @core.pyqtSlot(str)
    def on_keepCleanModeComboBox_currentIndexChanged(self, mode):
        self.send_acquisition_settings()

    @core.pyqtSlot(int)
    def on_takeBackgroundCheckBox_stateChanged(self, state):
        self.send_acquisition_settings()

    @core.pyqtSlot()
    def on_flipPumpOnlyPumpProbeButton_clicked(self):
        self.flipPumpOnlyPumpProbe.emit()

class Acquirer(core.QObject):
    getBackground = core.pyqtSignal()
    startAcq = core.pyqtSignal(np.ndarray)
    startDisplay = core.pyqtSignal()
    abortAcq = core.pyqtSignal()
    abortDisplay = core.pyqtSignal()

    acquisition_settings = core.pyqtSignal(dict)
    acquisition_timings = core.pyqtSignal(float, float, float, float, bool)

    new_pump_probe = core.pyqtSignal(np.ndarray, np.ndarray)
    new_probe_only = core.pyqtSignal(np.ndarray, np.ndarray)

    def __init__(self, cam):
        core.QObject.__init__(self)

        # cam already inited and in another thread
        self.cam = cam
        self.acquisition_settings.connect(self.cam.prep_acquisition_dict)
        self.cam.acquisition_timings.connect(self.prep_timings)
        self.getBackground.connect(self.cam.get_background)
        self.startAcq.connect(self.cam.scan_until_abort)
        self.abortAcq.connect(self.cam.abort)

        # Make this available without referencing cam directly
        self.abortion_done = self.cam.abortion_done 

        # Create event loop for self so that incoming signals are queued
        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)
        self.thread.started.connect(self.make_running)
        self.running = False
        atexit.register(self.__del__)

    def make_running(self):
        self.running = True

    def prep_acquisition(self, acq_mode, read_mode, exp_time, accum_time,
                    n_accums, kin_time, n_kinetics, trigger, keep_clean_mode,
                    backg_subtr):
        if acq_mode == "Scan until abort":
            acq_mode = "scan_until_abort"
        else:
            raise NotImplementedError("acq_mode %r" % acq_mode)

        if read_mode == "Full vertical binning":
            read_mode = "fullbin"
        else:
            raise NotImplementedError("read_mode %r" % read_mode)

        # Convert from ms to seconds
        exp_time /= 1000
        accum_time /= 1000
        kin_time /= 1000

        trigger = str(trigger).lower()
        keep_clean_mode = str(keep_clean_mode).lower().replace(" ", "_")

        # Don't even pass the accum/kinetic settings to prep_acquisition! TODO
        # later, maybe
        settings = {"acq_mode": acq_mode, "read_mode": read_mode,
            "exp_time": exp_time, "trigger": trigger}
        if trigger == "external":
            settings["keep_clean_mode"] = keep_clean_mode

        self.acquisition_settings.emit(settings)

        if backg_subtr:
            self.start_whole_exposure = self.get_background
        else:
            self.background = np.zeros(self.cam.x, dtype=np.int32)
            self.start_whole_exposure = self.continue_with_exposure

    def prep_timings(self, exp, accum, kin, readout, keep_clean, trigger):
        min_trigger_period = kin if trigger == "external" else -1.
        enable_keepCleanModeComboBox = True if trigger == "external" else False
        self.acquisition_timings.emit(exp, accum, kin, min_trigger_period,
            enable_keepCleanModeComboBox)

    def on_start(self):
        self.start_whole_exposure()

    def get_background(self):
        self.cam.acquisition_done.connect(self.store_backg_and_continue)
        self.getBackground.emit()

    def store_backg_and_continue(self, background):
        self.cam.acquisition_done.disconnect(self.store_backg_and_continue)
        self.background = background[0] # shape: (1, 1024) -> (1024,)
        self.continue_with_exposure()

    def continue_with_exposure(self):
        self.data_pair = self.cam.get_new_array(n_images=2)
        self.pump_probe_data = self.data_pair[0]
        self.probe_only_data = self.data_pair[1]
        self.next_data_has_pump = True

        self.cam.new_images.connect(self.send_new_images)
        self.wavelen_arr = self.cam.get_wavelen_array()

        self.startAcq.emit(self.data_pair) # get 2 images at a time

        # Tell listeners to start displaying data too
        self.startDisplay.emit()

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

    def on_flip(self):
        self.next_data_has_pump = not self.next_data_has_pump
        self.probe_only_data, self.pump_probe_data = (
            self.pump_probe_data, self.probe_only_data)

    def on_abort(self):
        self.cam.new_images.disconnect(self.send_new_images)
        self.abortAcq.emit()
        self.abortDisplay.emit()

        del self.background
        del self.data_pair, self.pump_probe_data, self.probe_only_data
        del self.next_data_has_pump
        del self.wavelen_arr

    def __del__(self):
        if self.running:
            self.thread.quit()