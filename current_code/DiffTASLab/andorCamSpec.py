# Gabriel Ehrlich
# gabriel.s.ehrlich@gmail.com
# 28 September 2015

"""Define a widget for starting Andor camera acquisitions

This module defines two interacting classes that define a GUI for
setting up, starting, and aborting acquisitions taken with an Andor
camera.
- AcquisitionWidget: GUI thread stuff.
- Acquirer: worker thread.
See the documentation for cam_control for more detail on the division of
labor between these two classes.
"""

from __future__ import print_function
from PyQt4 import QtCore as core, QtGui as gui, uic
import numpy as np
import warnings
from contextlib import contextmanager
import atexit
import time

ui_filename = "andorCamSpec.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)


class AndorCamSpecWidget(gui.QWidget, Ui_Widget):
    """Controls GUI elements and dispatches events/signals."""
    throwMessage                = core.pyqtSignal(str, int, name='throwMessage')
    getBackground               = core.pyqtSignal()
    start                       = core.pyqtSignal()
    abort                       = core.pyqtSignal()
    reconnect_edit_signals      = core.pyqtSignal(bool)
    reconnect_active_signals    = core.pyqtSignal(bool)
    
    # acquisition_settings = core.pyqtSignal(str, str, float, float, int, float,
    #     int, str, str, bool)
    acquisition_settings = core.pyqtSignal(dict, bool)

    # new_pump_probe = core.pyqtSignal(np.ndarray, np.ndarray)
    # new_probe_only = core.pyqtSignal(np.ndarray, np.ndarray)
    new_data = core.pyqtSignal(np.ndarray, np.ndarray, bool)

    flipPumpOnlyPumpProbe = core.pyqtSignal()

    acq_modes = {
        "Single":           "single",
        "Accumulate:":      "accum",
        "Kinetic series":   "kinetic",
        "Scan until abort": "scan_until_abort"
    }

    trigger_modes = {
        "Internal":         "internal",
        "External":         "external",
        "External start":   "external_start"
    }

    read_modes = {
        "Image":                    "image",
        "Full vertical binning":    "fullbin"
    }

    keep_clean_modes = {
        "Wait":             "wait",
        "Trigger abort":    "trigger_abort",
        "Disable":          "disable"
    }

    def __init__(self, cams, specs, acquiring=False):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        
        # Set up stationary parts of the GUI.
        self.cam_dict = {cams[i].name: i for i in range(len(cams))}
        self.cam_list = []
        self.spec_list = []
        for cam in cams:
            self.cam_list.append(cam.name)
        for spec in specs:
            self.spec_list.append(spec.name)
        self.spec_dict = {specs[i].name: i for i in range(len(specs))}
        #self.spec_list = self.spec_dict.keys()

        # SetupUi crashes on QComboBoxes, so add them manually here
        self.cams       = cams
        self.specs      = specs
        # self.actcam     = self.cams[0]
        # self.actspec    = self.actcam.spec
        # self.editcam    = self.cams[0]
        # self.editspec   = self.editcam.spec
        self.actcam         = 0
        self.editcam        = 0
        self.prev_actcam    = self.actcam
        self.prev_editcam   = self.editcam
        self.cams[self.editcam].has_edit_focus = True
        self.cams[self.actcam].has_active_focus = True

        self.is_first_time = True
        for cam in self.cams:
            cam.parameter_setting_done.connect(self.update_gui)

        self.editCameraComboBox.addItems(self.cam_list)
        self.editCameraComboBox.setCurrentIndex(self.editcam)

        self.triggerSourceComboBox.addItems(self.trigger_modes.keys())
        self.keepCleanModeComboBox.addItems(self.keep_clean_modes.keys())
        self.keepCleanModeComboBox.setEnabled(True)

        # ONLY AVAILABLE ON NEWTON IN FVB EXTERNAL TRIGGER MODE
        # if self.actcam.name == "Newton01":
        #     self.keepCleanModeComboBox.addItem("Disable")

        self.setTempSpinBox.setValue(self.cams[self.editcam].parms["set_temperature"])
        self.setTempSpinBox.setRange(*self.cams[self.editcam].parms["temp_limits"])
        self.setTempSpinBox.setEnabled(True)

        self.attachedSpecInfo.setText(self.cams[self.editcam].spec.name)
        self.activeGratingComboBox.addItems(["1", "2"])
        self.shutterStateComboBox.addItems(["Open", "Closed"])
        
        self.activeCameraComboBox.addItems(self.cam_list)
        self.activeCameraComboBox.setCurrentIndex(self.actcam)

        # Allow only sensible inputs for lineedits
        self.setExposureTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.setAccumTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.setKinTimeLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.setSlitwidthLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))
        self.setWavelengthLineEdit.setValidator(gui.QDoubleValidator(
            0, 10000, 2))

        # Connect GUI signals that aren't automatically connected
        
        self.controller = CameraController(self)
        self.acquirer   = Acquirer(self)
        
        # self.editCameraComboBox.currentIndexChanged.connect(
        #     self.on_editCameraComboBox_currentIndexChanged)
        # self.activeCameraComboBox.currentIndexChanged.connect(
        #     self.on_activeCameraComboBox_currentIndexChanged)
        # self.triggerSourceComboBox.currentIndexChanged.connect(
        #     self.on_triggerSourceComboBox_currentIndexChanged)
        # self.keepCleanModeComboBox.currentIndexChanged.connect(
        #     self.on_keepCleanModeComboBox_currentIndexChanged)
        self.setTempButton.clicked.connect(
            self.controller.on_cooldownButton_clicked)
        self.coolerOffButton.clicked.connect(
            self.controller.on_coolerOffButton_clicked)
        
        # For making read-only during acquisition
        self.enabled_input_widgets = (
            self.editCameraComboBox,
            self.activeCameraComboBox,
            self.labelExposureTime,
            self.setExposureTimeLineEdit,
            self.labelTriggerSource,
            self.triggerSourceComboBox,
            self.labelKeepCleanMode,
            self.keepCleanModeComboBox,
            self.takeBackgroundCheckBox
            )

        # Create worker and connect signals/slots
        self.reconnect_edit_signals.connect(self.controller.reconnect_signals)
        self.reconnect_active_signals.connect(self.acquirer.reconnect_signals)
        self.acquisition_settings.connect(self.controller.set_acq_parameters)
        self.start.connect(self.acquirer.on_start)
        self.flipPumpOnlyPumpProbe.connect(self.acquirer.on_flip)
        self.abort.connect(self.acquirer.on_abort)
        #self.controller.acquisition_timings.connect(self.update_timing)
        self.acquirer.abortion_done.connect(self.finish_abortion)

        # Allow other objects to connect these signals without referenc-
        # ing controller directly
        self.startAcq       = self.acquirer.startAcq
        self.startDisplay   = self.acquirer.startDisplay
        self.abortAcq       = self.acquirer.abortAcq
        self.abortDisplay   = self.acquirer.abortDisplay
        self.new_data       = self.acquirer.new_data


        # Prepare to receive GUI instructions from controller
        # self.controller.set_enabled.connect(self.set_enabled,
        #     type=core.Qt.BlockingQueuedConnection)
        self.controller.set_text.connect(self.set_text,
                                        type=core.Qt.BlockingQueuedConnection)
        # self.controller.set_tempSpin_value_range.connect(
        #     self.set_tempSpin_value_range,
        #     type=core.Qt.BlockingQueuedConnection)
        self.reconnect_edit_signals.emit(self.is_first_time)
        self.reconnect_active_signals.emit(self.is_first_time)
        # Fill in real exposure times
        self.send_acquisition_settings()
        self.is_first_time = False

        # If a bad shutdown somehow left the camera acquiring, allow the
        # user to abort it
        if acquiring:
            self.set_acquisition_gui()
    
    def set_enabled(self, widget, val):
        """Slot for controller's set_text signal"""
        widget.setEnabled(val)

    def set_text(self, widget, text):
        """Slot for controller's set_enabled signal"""
        widget.setText(text)

    def printcams(self):
        print("act: " + str(self.actcam) + " edit: " + str(self.editcam) + "\n")

    def send_acquisition_settings(self):
        """Tell the worker new parameters for cam.prep_acquisition"""
        
        parms = self.cams[self.editcam].parms

        if self.is_first_time == False:
            
            # parms["acq_mode"]         = self.acq_modes[self.acquisitionModeComboBox.currentText()]
            # parms["read_mode"]        = self.read_modes[self.readModeComboBox.currentText()]
            parms["acq_mode"]         = "scan_until_abort"
            parms["read_mode"]        = "fullbin"
            # convert times rom ms to s
            parms["exp_time"]         = float(self.setExposureTimeLineEdit.text())
            
            # set timings appropriate for acquisition modes
            # if set wrong, driver crashes
            if parms["acq_mode"] == "single":
                parms["accum_cycle_time"] = None
                parms["n_accums"]         = None
                parms["kin_cycle_time"]   = None
                parms["n_kinetics"]       = None

            if parms["acq_mode"] == "accum":
                parms["accum_cycle_time"] = float(self.setAccumTimeLineEdit.text())
                parms["n_accums"]         = self.nAccumsSpinBox.value()
                parms["kin_cycle_time"]   = None
                parms["n_kinetics"]       = None
            
            if parms["acq_mode"] == "kinetic":
                parms["accum_cycle_time"] = float(self.setAccumTimeLineEdit.text())
                parms["n_accums"]         = self.nAccumsSpinBox.value()
                parms["kin_cycle_time"]   = float(self.setKinTimeLineEdit.text())
                parms["n_kinetics"]       = self.nKineticsSpinBox.value()
            
            if parms["acq_mode"] == "scan_until_abort":
                parms["accum_cycle_time"] = None
                parms["n_accums"]         = None
                parms["kin_cycle_time"]   = float(self.setKinTimeLineEdit.text())
                parms["n_kinetics"]       = None
            
            parms["trigger"]          = self.trigger_modes[str(self.triggerSourceComboBox.currentText())]
            parms["keep_clean_mode"]  = self.keep_clean_modes[str(self.keepCleanModeComboBox.currentText())]
        
            if bool(self.takeBackgroundCheckBox.isChecked()):
                parms["background_nth_acq"] = float(self.nBackgroundsSpinBox.value())
            else:
                parms["background_nth_acq"] = -1.

            #parms[set_temperature]  = self.setTempSpinBox.value()

        self.acquisition_settings.emit(parms, self.is_first_time)


    # def update_timing(self, exp, accum, kin, min_trigger_period,
    #         enable_keepCleanModeComboBox):
    #     """Update the GUI fields with timings corrected by the camera"""
    #     self.setExposureTimeLineEdit.setText("{:.2f}".format(exp * 1000))
    #     self.setAccumTimeLineEdit.setText("{:.2f}".format(accum * 1000))
    #     self.setKinTimeLineEdit.setText("{:.2f}".format(kin * 1000))

    #     # Pass -1. for min_trigger_period if it doesn't apply
    #     if min_trigger_period == -1.:
    #         self.minTriggerPeriodLabel.setText("N/A")
    #         self.minTriggerPeriodLabel.setEnabled(False)
    #         self.labelMinTriggerPeriod.setEnabled(False)
    #     else:
    #         self.minTriggerPeriodLabel.setText("{:.2f} ms".format(
    #             min_trigger_period*1000))
    #         self.minTriggerPeriodLabel.setEnabled(True)
    #         self.labelMinTriggerPeriod.setEnabled(True)

    #     # Also allow the user to change the keep clean mode while in
    #     # external mode (and not in internal mode because ignored)
        
    #     self.labelKeepCleanMode.setEnabled(enable_keepCleanModeComboBox)
    #     self.keepCleanModeComboBox.setEnabled(enable_keepCleanModeComboBox)

    def update_gui(self):
        parms = self.cams[self.editcam].parms
        """Update the GUI fields with timings corrected by the camera"""
        self.setExposureTimeLineEdit.setText("{:.2f}".format(float(parms["exp_time"])))

        if parms["accum_cycle_time"] is not None:
            self.setAccumTimeLineEdit.setText("{:.2f}".format(float(parms["accum_cycle_time"])))
            self.setAccumTimeLineEdit.setEnabled(True)
        else:
            self.setAccumTimeLineEdit.setText("N/A")
            self.setAccumTimeLineEdit.setEnabled(False)
        
        if parms["kin_cycle_time"] is not None:
            self.setKinTimeLineEdit.setText("{:.2f}".format(float(parms["kin_cycle_time"])))
            self.setKinTimeLineEdit.setEnabled(True)
        else:
            self.setKinTimeLineEdit.setText("N/A")
            self.setKinTimeLineEdit.setEnabled(False)
        
        if parms["trigger"] == "external":
            min_trigger_period = float(parms["kin_cycle_time"]) 
        else:
            min_trigger_period = -1.
        
        # Pass -1. for min_trigger_period if it doesn't apply
        if min_trigger_period == -1.:
            self.minTriggerPeriodLabel.setText("N/A")
            self.minTriggerPeriodLabel.setEnabled(False)
            self.labelMinTriggerPeriod.setEnabled(False)
        else:
            self.minTriggerPeriodLabel.setText("{:.2f} ms".format(
                min_trigger_period))
            self.minTriggerPeriodLabel.setEnabled(True)
            self.labelMinTriggerPeriod.setEnabled(True)

        # Also allow the user to change the keep clean mode while in
        # external mode (and not in internal mode because ignored)
        
        #self.labelKeepCleanMode.setEnabled(enable_keepCleanModeComboBox)
        #self.keepCleanModeComboBox.setEnabled(enable_keepCleanModeComboBox)



    @core.pyqtSlot()
    def on_startButton_clicked(self):
        self.send_acquisition_settings()
        self.set_acquisition_gui()
        self.start.emit()
    
    # @core.pyqtSlot()
    # def on_setTempButton_clicked(self):
    #     if int(self.setTempSpinBox.value()) != self.editcam.parms["set_temperature"]:
    #         # set new temperature and tell camera to change it...
    #         self.editcam.parms["set_temperature"] = int(self.setTempSpinBox.value())
    #         self.editcam.cooldown(self.editcam.parms["set_temperature"])
            

    def set_acquisition_gui(self):
        """Turn everything off except abort and flip, which turn on"""
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
        """Re-enable buttons once abortion is done"""
        for widget in self.enabled_input_widgets:
            widget.setEnabled(True)
        self.startButton.setEnabled(True)

    @core.pyqtSlot()
    def on_setExposureTimeLineEdit_editingFinished(self):
        self.send_acquisition_settings()
    
    @core.pyqtSlot()
    def on_setAccumTimeLineEdit_editingFinished(self):
        self.send_acquisition_settings()
    
    @core.pyqtSlot()
    def on_setKinTimeLineEdit_editingFinished(self):
        self.send_acquisition_settings()
    
    @core.pyqtSlot()
    def on_setSlitwidthLineEdit_editingFinished(self):
        self.send_acquisition_settings()
    
    @core.pyqtSlot()
    def on_setWavelengthLineEdit_editingFinished(self):
        self.send_acquisition_settings()
    
    @core.pyqtSlot(str)
    def on_editCameraComboBox_currentIndexChanged(self, mode):
        self.prev_editcam = self.editcam
        self.editcam = self.editCameraComboBox.currentIndex()
        self.attachedSpecInfo.setText(self.cams[self.editcam].spec.name)
        for cam in self.cams:
            cam.has_edit_focus = False
       
        self.cams[self.editcam].has_edit_focus = True
        self.reconnect_edit_signals.emit(self.is_first_time)
        self.send_acquisition_settings()
        

    @core.pyqtSlot(str)
    def on_activeCameraComboBox_currentIndexChanged(self, mode):
        self.prev_actcam = self.actcam
        self.actcam = self.activeCameraComboBox.currentIndex()
        for cam in self.cams:
            cam.has_active_focus = False
        
        self.cams[self.actcam].has_active_focus = True
        self.reconnect_active_signals.emit(self.is_first_time)
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
    """Sends instructions to the camera/spectro and monitors them"""
    getBackground = core.pyqtSignal()
    startAcq = core.pyqtSignal(np.ndarray)
    startDisplay = core.pyqtSignal()
    abortAcq = core.pyqtSignal()
    abortDisplay = core.pyqtSignal()
    reconnect_active_signals = core.pyqtSignal()
    
    #acquisition_settings = core.pyqtSignal(dict, bool)
    #acquisition_timings = core.pyqtSignal(float, float, float, float, bool)

    new_data = core.pyqtSignal(np.ndarray, np.ndarray, np.ndarray, bool)
    
    def __init__(self, widget):
        core.QObject.__init__(self)

        # cam already inited and in another thread
        self.widget = widget
        #self.cams   = self.widget.cams
        # self.acquisition_settings.connect(self.actcam.prep_acquisition_dict)
        #self.acquisition_settings.connect(self.actcam.set_acq_parameters)
        #self.actcam.acquisition_timings.connect(self.prep_timings)
        # for i in range(len(self.widget.cams)):
        #     self.getBackground.connect(self.widget.cams[i].get_background)
        #     self.startAcq.connect(self.widget.cams[i].scan_until_abort)
        #     self.abortAcq.connect(self.widget.cams[i].abort)

        # Make this available without referencing cam directly
        self.abortion_done = self.widget.cams[self.widget.actcam].abortion_done 

        # Create event loop for self so that incoming signals are queued
        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)
        #self.thread.started.connect(self.make_timer)
        self.running = False
        atexit.register(self.__del__)

    # def make_timer(self):
    #     """Wait until after __init__ to make timer so it's in new thread"""
    #     # Create and connect a timer to update the camera status etc.
    #     self.status_timer = core.QTimer()
    #     self.status_timer.setInterval(16)
    #     self.status_timer.timeout.connect(self.update_camera_status_temp)

    #     # Also keep track of whether self.close has been called yet
    #     self.running = True

    # def make_running(self):
    #     self.running = True

    # def update_camera_status_temp(self):
    #     """Tell the widget the camera status and temp to display"""
    #     status = self.actcam.get_status()
    #     self.set_text.emit(self.widget.cameraStatusLabel, status)

    #     if "ACQUIRING" in status and self.cam.name == "iDus01":
    #         self.set_text.emit(self.widget.tempLabel, "unknown")
    #         self.set_text.emit(self.widget.coolerLabel,
    #             "iDus01 can't check temp right now")
    #     else:
    #         temp, cooler_status = self.cam.get_temp()
    #         self.set_text.emit(self.widget.tempLabel, str(temp))
    #         self.set_text.emit(self.widget.coolerLabel, cooler_status)

    # def prep_acquisition(self, parms, is_first_time):
    #     """Interpret GUI input and tell cam the appropriate settings"""
    #     # Acquisition mode: currently only scan until abort works
    #     # because when the other modes terminate the GUI wouldn't know
    #     # that the acquisition is done.
    #     # if acq_mode == "Scan until abort":
    #     #     acq_mode = "scan_until_abort"
    #     # else:
    #     #     raise NotImplementedError("acq_mode %r" % acq_mode)

    #     # # Read mode: currently only full vertical binning works because
    #     # # the spectra plotters assume a 1-dimensional array.
    #     # if read_mode == "Full vertical binning":
    #     #     read_mode = "fullbin"
    #     # else:
    #     #     raise NotImplementedError("read_mode %r" % read_mode)

    #     # # Convert from ms to seconds
    #     # exp_time /= 1000
    #     # accum_time /= 1000
    #     # kin_time /= 1000

    #     # trigger = str(trigger).lower()
    #     # keep_clean_mode = str(keep_clean_mode).lower().replace(" ", "_")

    #     # # Don't even pass the accum/kinetic settings to prep_acquisition
    #     # # because we're mostly externally triggering anyway. TODO if
    #     # # different behavior is desired.
    #     # settings = {"acq_mode": acq_mode, "read_mode": read_mode,
    #     #     "exp_time": exp_time, "trigger": trigger}
    #     # if trigger == "external":
    #     #     settings["keep_clean_mode"] = keep_clean_mode

    #     # Queue a call to cam.prep_acquisition
    #     self.acquisition_settings.emit(parms, is_first_time)
        
    #     # Set which of self's methods to call upon acquisition start
    #     if (float(parms["background_nth_acq"]) != -1.):
    #         self.start_whole_exposure = self.get_background
    #     else:
    #         self.background = np.zeros(self.cams[self.actcam].x, dtype=np.int32)
    #         self.start_whole_exposure = self.continue_with_exposure


    # def prep_timings(self, exp, accum, kin, readout, keep_clean, trigger):
    #     """Send the camera's corrected timings back to the GUI"""
    #     min_trigger_period = kin if trigger == "external" else -1.
    #     enable_keepCleanModeComboBox = True if trigger == "external" else False
    #     self.acquisition_timings.emit(exp, accum, kin, min_trigger_period,
    #         enable_keepCleanModeComboBox)

    def reconnect_signals(self, is_first_time):
        # disconnect slots from previous camera and reconnect to actual camera

        # upon initialization, do not disconnect anything...
        if is_first_time:
            self.getBackground.connect(self.widget.cams[self.widget.actcam].get_background)
            self.startAcq.connect(self.widget.cams[self.widget.actcam].scan_until_abort)
            self.abortAcq.connect(self.widget.cams[self.widget.actcam].abort)
        else:
            # disconnect first
            self.getBackground.disconnect(self.widget.cams[self.widget.prev_actcam].get_background)
            self.startAcq.disconnect(self.widget.cams[self.widget.prev_actcam].scan_until_abort)
            self.abortAcq.disconnect(self.widget.cams[self.widget.prev_actcam].abort)
            # then reconnect to actual cam
            self.getBackground.connect(self.widget.cams[self.widget.actcam].get_background)
            self.startAcq.connect(self.widget.cams[self.widget.actcam].scan_until_abort)
            self.abortAcq.connect(self.widget.cams[self.widget.actcam].abort)
            self.abortion_done = self.widget.cams[self.widget.actcam].abortion_done 

        

    def on_start(self):
        """Slot for GUI's start signal"""
        self.start_whole_exposure()

    def get_background(self):
        """Called in background subtraction mode upon acq. start"""
        # Tell self.thread what to do when the cam is done getting
        # the background
        self.widget.cams[self.widget.actcam].acquisition_done.connect(self.store_backg_and_continue)
        # Queue a call to cam.get_background
        self.getBackground.emit()

    def store_backg_and_continue(self, background):
        """Receive the background array and proceed with acqusition"""
        # Disconnect the slot connected above
        self.widget.cams[self.widget.actcam].acquisition_done.disconnect(self.store_backg_and_continue)
        # Store the background and continue
        #self.background = background[0] # shape: (1, 1024) -> (1024,)
        self.background = np.transpose(background) # shape: (1, 1024) -> (1024, 1)
        self.continue_with_exposure()

    def continue_with_exposure(self):
        """Called once the background is set/measured to continue acq"""
        # Allocate space to give to scan_until_abort, and name the two
        # rows appropriately.
        actcam = self.widget.cams[self.widget.actcam]
        self.data_pair = actcam.get_new_array(n_images=2)
        self.pump_probe_data = self.data_pair[0]
        self.probe_only_data = self.data_pair[1]
        # Keep track of which image will be updated next
        self.next_data_has_pump = True

        # Tell self.thread what to do when the camera has new images
        actcam.new_images.connect(self.send_new_images)

        # Get the current array of wavelengths from cam
        self.wavelen_arr = actcam.get_wavelen_array()

        # Queue a call to cam.scan_until_abort
        #self.startAcq.emit(self.data_pair)
        self.startAcq.emit(self.data_pair)

        # Tell listeners (plotting widgets) to start displaying data too
        self.startDisplay.emit()

    def send_new_images(self, n_new):
        """Slot for cam.new_images. Background-correct and pass on"""
        if n_new == 1:
            if self.next_data_has_pump:
                #self.pump_probe_data -= self.background
                #self.new_pump_probe.emit(self.wavelen_arr,
                #    self.pump_probe_data - self.background)
                # self.new_data.emit(self.wavelen_arr,
                #                 self.pump_probe_data - self.background, 
                #                 self.next_data_has_pump)
                self.new_data.emit(self.wavelen_arr,
                                self.pump_probe_data,
                                self.background, 
                                self.next_data_has_pump)
                self.next_data_has_pump = False
            else:
                #self.new_probe_only.emit(self.wavelen_arr,
                #    self.probe_only_data - self.background)
                # self.new_data.emit(self.wavelen_arr,
                #                 self.probe_only_data - self.background, 
                #                 self.next_data_has_pump)
                self.new_data.emit(self.wavelen_arr,
                                self.probe_only_data,
                                self.background, 
                                self.next_data_has_pump)
                self.next_data_has_pump = True
        else: # n_new == 2
            #self.new_probe_only.emit(self.wavelen_arr,
            #    self.probe_only_data - self.background)
            #self.new_pump_probe.emit(self.wavelen_arr,
            #    self.pump_probe_data - self.background)
            # self.new_data.emit(self.wavelen_arr,
            #                     self.probe_only_data - self.background, 
            #                     self.next_data_has_pump)
            # self.new_data.emit(self.wavelen_arr,
            #                     self.pump_probe_data - self.background, 
            #                     self.next_data_has_pump)
            self.new_data.emit(self.wavelen_arr,
                                self.probe_only_data,
                                self.background, 
                                self.next_data_has_pump)
            self.new_data.emit(self.wavelen_arr,
                                self.pump_probe_data,
                                self.background, 
                                self.next_data_has_pump)

    def on_flip(self):
        """Slot. Switch what is pump-probe and what is pump-only"""
        self.next_data_has_pump = not self.next_data_has_pump
        self.probe_only_data, self.pump_probe_data = (
            self.pump_probe_data, self.probe_only_data)

    def on_abort(self):
        """Stop listening to the camera, stop acquiring, and clean up"""
        actcam = self.widget.cams[self.widget.actcam]
        try:
            actcam.new_images.disconnect(self.send_new_images)
        except TypeError:
            # The abort button was probably pressed mid-backg collection
            actcam.acquisition_done.disconnect(
                self.store_backg_and_continue)
        else:
            # This will throw errors if only the background collection
            # has started when abort is pressed
            self.abortDisplay.emit()
            del self.background
            del self.data_pair, self.pump_probe_data, self.probe_only_data
            del self.next_data_has_pump
            del self.wavelen_arr
        finally:
            # Definitely make sure the acquisition is actually aborted
            self.abortAcq.emit()

    def __del__(self):
        if self.running:
            self.thread.quit()


class CameraController(core.QObject):
    """Sends instructions to the camera/spectro and monitors them"""
    spec_initialize             = core.pyqtSignal()
    cam_initialize              = core.pyqtSignal()
    cam_initialize_done         = core.pyqtSignal(bool) # first arg: acquiring
    cool_down                   = core.pyqtSignal(int)
    cooler_off                  = core.pyqtSignal()
    cam_shut_down               = core.pyqtSignal()
    spec_shut_down              = core.pyqtSignal()
    done_closing                = core.pyqtSignal()
    set_enabled                 = core.pyqtSignal(gui.QWidget, bool)
    set_text                    = core.pyqtSignal(gui.QWidget, str)
    set_tempSpin_value_range    = core.pyqtSignal(int, int, int)
    acquisition_settings        = core.pyqtSignal(dict, bool)
    reconnect_edit_signals      = core.pyqtSignal()
    status_timer_stop           = core.pyqtSignal()

    def __init__(self, widget):
        core.QObject.__init__(self)

        self.widget = widget
        self.cams = self.widget.cams
        # set editcam to actual (initial) number
        # change that later dynamically
        self.editcam = self.widget.editcam
        self.actcam = self.widget.actcam
        self.last_editcam = self.editcam

        # self.all_buttons = (
        #     self.widget.initAllButton,
        #     self.widget.cooldownButton,
        #     self.widget.coolerOffButton,
        #     self.widget.restartCamButton,
        #     self.widget.restartAllButton
        #     )
        self.all_buttons = ()

        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)
        self.thread.started.connect(self.make_timer)
        self.running = False
        atexit.register(self.close)

        # Connect signals to the camera's slots
        # self.spec_initialize.connect(self.cam.spec.initialize,
        #     type=core.Qt.BlockingQueuedConnection)
        # self.cam_initialize.connect(self.cam.initialize,
        #     type=core.Qt.BlockingQueuedConnection)
        # for i in range(len(self.widget.cams)):
        #     self.acquisition_settings.connect(self.widget.cams[i].set_acq_parameters,
        #                             type=core.Qt.BlockingQueuedConnection)
        #     self.cool_down.connect(self.widget.cams[i].cooldown,
        #                             type=core.Qt.BlockingQueuedConnection)
        #     self.cooler_off.connect(self.widget.cams[i].cooler_off,
        #                             type=core.Qt.BlockingQueuedConnection)
        #self.reconnect_cam_signals.emit()
        for i in range(len(self.widget.cams)):
            self.cam_shut_down.connect(self.widget.cams[i].shut_down,
                                        type=core.Qt.BlockingQueuedConnection)
            self.spec_shut_down.connect(self.widget.cams[i].spec.shut_down,
                                        type=core.Qt.BlockingQueuedConnection)
            # self.cam_shut_down.connect(self.widget.cams[i].shut_down)
            # self.spec_shut_down.connect(self.widget.cams[i].spec.shut_down)

    def reconnect_signals(self, is_first_time):
        # disconnect slots from previous camera and reconnect to actual camera

        # upon initialization, do not disconnect anything...
        if is_first_time:
            self.acquisition_settings.connect(self.widget.cams[self.widget.editcam].set_acq_parameters,
                                            type=core.Qt.BlockingQueuedConnection)
            self.cool_down.connect(self.widget.cams[self.widget.editcam].cooldown,
                                            type=core.Qt.BlockingQueuedConnection)
            self.cooler_off.connect(self.widget.cams[self.widget.editcam].cooler_off,
                                            type=core.Qt.BlockingQueuedConnection)
        else:
            # disconnect first
            self.acquisition_settings.disconnect(self.widget.cams[self.widget.prev_editcam].set_acq_parameters)
            self.cool_down.disconnect(self.widget.cams[self.widget.prev_editcam].cooldown)
            self.cooler_off.disconnect(self.widget.cams[self.widget.prev_editcam].cooler_off)
            # then reconnect to actual cam
            self.acquisition_settings.connect(self.widget.cams[self.widget.editcam].set_acq_parameters,
                                            type=core.Qt.BlockingQueuedConnection)
            self.cool_down.connect(self.widget.cams[self.widget.editcam].cooldown,
                                            type=core.Qt.BlockingQueuedConnection)
            self.cooler_off.connect(self.widget.cams[self.widget.editcam].cooler_off,
                                            type=core.Qt.BlockingQueuedConnection)
            


    def make_timer(self):
        """Wait until after __init__ to make timer so it's in new thread"""
        # Create and connect a timer to update the camera status etc.
        self.status_timer = core.QTimer()
        self.status_timer.setInterval(16)
        self.status_timer.timeout.connect(self.update_camera_status_temp)
        self.status_timer_stop.connect(self.status_timer.stop)
        self.status_timer.start()
        # Also keep track of whether self.close has been called yet
        self.running = True

    def set_acq_parameters(self, parms, is_first_time):
        """Interpret GUI input and tell cam the appropriate settings"""
        # Queue a call to cam.prep_acquisition

        self.acquisition_settings.emit(parms, is_first_time)
        
        # Set which of self's methods to call upon acquisition start
        if (float(parms["background_nth_acq"]) != -1.):
            self.widget.acquirer.start_whole_exposure = self.widget.acquirer.get_background
        else:
            self.widget.acquirer.background = np.zeros(self.widget.cams[self.widget.actcam].x, dtype=np.int32)
            self.widget.acquirer.start_whole_exposure = self.widget.acquirer.continue_with_exposure



    def on_initAllButton_clicked(self):
        self.set_enabled.emit(self.widget.initAllButton, False)
        with self.all_buttons_disabled():
            # Initialize and reigster the spectrometer
            self.init_spec()

            # Do all the cam initialization stuff
            self.init_cam()

        # Enable relevant buttons that were disabled on startup
        self.set_enabled.emit(self.widget.setTempButton, True)
        #self.set_enabled.emit(self.widget.restartCamButton, True)
        #self.set_enabled.emit(self.widget.restartAllButton, True)

    def on_cooldownButton_clicked(self):
        if int(self.widget.setTempSpinBox.value()) != int(self.cams[self.widget.editcam].parms["set_temperature"]):
            # set new temperature and tell camera to change it...
            self.cams[self.widget.editcam].parms["set_temperature"] = int(self.widget.setTempSpinBox.value())
        else:
            return

        with self.all_buttons_disabled():
            # if self.last_editcam != self.editcam:
            #     self.cool_down.disconnect(self.widget.cams[self.last_editcam].cooldown)
            # else:
            #     self.last_editcam = self.editcam 
            #     self.cool_down.connect(self.widget.cams[self.editcam].cooldown,
            #                             type=core.Qt.BlockingQueuedConnection)
            
            self.cool_down.emit(self.widget.cams[self.editcam].parms["set_temperature"])

        # Allow the user to turn off the cooler
        self.set_enabled.emit(self.widget.coolerOffButton, True)

    def on_coolerOffButton_clicked(self):
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        with self.all_buttons_disabled():
            # if self.last_editcam != self.editcam:
            #     self.cooler_off.disconnect(self.widget.cams[self.editcam].cooler_off)
            # else:
            #     self.last_editcam = self.editcam 
            #     self.cooler_off.connect(self.widget.cams[self.editcam].cooler_off,
            #                             type=core.Qt.BlockingQueuedConnection)
            
            self.cooler_off.emit()

    # def on_restartCamButton_clicked(self):
    #     self.set_enabled.emit(self.widget.cooldownButton, False)
    #     self.set_enabled.emit(self.widget.coolerOffButton, False)
    #     self.set_enabled.emit(self.widget.restartCamButton, False)
    #     self.set_enabled.emit(self.widget.restartAllButton, False)
    #     self.set_enabled.emit(self.widget.tempSpin, False)

    #     self.shut_down_cam()
    #     self.init_cam()

    #     self.set_enabled.emit(self.widget.cooldownButton, True)
    #     self.set_enabled.emit(self.widget.restartCamButton, True)
    #     self.set_enabled.emit(self.widget.restartAllButton, True)

    # def on_restartAllButton_clicked(self):
    #     self.set_enabled.emit(self.widget.cooldownButton, False)
    #     self.set_enabled.emit(self.widget.coolerOffButton, False)
    #     self.set_enabled.emit(self.widget.restartCamButton, False)
    #     self.set_enabled.emit(self.widget.restartAllButton, False)
    #     self.set_enabled.emit(self.widget.tempSpin, False)

    #     self.shut_down_cam()
    #     self.shut_down_spec()
    #     self.init_spec()
    #     self.init_cam()

    #     self.set_enabled.emit(self.widget.cooldownButton, True)
    #     self.set_enabled.emit(self.widget.restartCamButton, True)
    #     self.set_enabled.emit(self.widget.restartAllButton, True)

    def update_camera_status_temp(self):
        """Tell the widget the camera status and temp to display"""
        status = self.widget.cams[self.widget.editcam].get_status()
        #self.set_text.emit(self.widget.cameraStatusLabel, status)
        
        if "ACQUIRING" in status and self.widget.cams[self.widget.editcam].name == "iDus01":
            #self.set_text.emit(self.widget.tempLabel, "unknown")
            self.set_text.emit(self.widget.actualTemperatureInfo, "N/A")
        else:
            temp, cooler_status = self.widget.cams[self.widget.editcam].get_temp()
            self.set_text.emit(self.widget.actualTemperatureInfo, str(temp))
            #self.set_text.emit(self.widget.coolerLabel, cooler_status)

    def init_spec(self):
        self.spec_initialize.emit()

    def init_cam(self):
        # Initalize the camera
        self.cam_initialize.emit()

        # Set allowed temp range and default, then enable
        self.set_tempSpin_value_range.emit(cam_info[self.cam.name]["temp"],
            *self.cam.get_temp_range())
        self.set_enabled.emit(self.widget.tempSpin, True)

        # Start checking the camera status
        self.status_timer.start()

        # If there was a sudden shutdown while the cooler was on last time,
        # let the user turn off the cooler
        if "OFF" not in self.cam.get_temp()[1]:
            self.set_enabled.emit(self.widget.coolerOffButton, True)

        # If a bad shutdown somehow left the camera acquiring, let the
        # user abort the acquisition by telling listeners that.
        self.cam_initialize_done.emit("ACQUIRING" in self.cam.get_status())

    def shut_down_cams(self):
        time.sleep(2)
        if self.status_timer.isActive():
            self.status_timer_stop.emit()
            
        self.cooler_off.emit()
        self.update_camera_status_temp()
        self.cam_shut_down.emit()

    def shut_down_spec(self):
        self.spec_shut_down.emit()

    def close(self):
        """If the camera/spectro were ever initialized, shut down"""
        if self.running:
            self.set_enabled.emit(self.widget.setTempButton, False)
            self.set_enabled.emit(self.widget.coolerOffButton, False)
            #self.set_enabled.emit(self.widget.restartCamButton, False)
            #self.set_enabled.emit(self.widget.restartAllButton, False)
            self.set_enabled.emit(self.widget.setTempSpinBox, False)

            # for cam in self.widget.cams:
            #     if cam.is_initialized(): self.shut_down_cams()
            #     if cam.spec.is_initialized(): self.shut_down_specs()
            self.shut_down_cams()
            self.shut_down_specs()

            self.done_closing.emit()
            self.thread.quit()
            self.running = False

    @contextmanager
    def all_buttons_disabled(self):
        """Enable or disable all buttons"""
        buttons_prev_enabled = []
        for button in self.all_buttons:
            if button.isEnabled():
                buttons_prev_enabled.append(button)
                self.set_enabled.emit(button, False)

        yield

        for button in buttons_prev_enabled:
            self.set_enabled.emit(button, True)

    def __del__(self):
        print("__del__ has been called")
        if self.running: self.close()
