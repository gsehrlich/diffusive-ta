from PyQt4 import QtCore as core, QtGui as gui, uic
import andor.andorcamera as cams
from andor._known import cam_info
import sys
from contextlib import contextmanager

default_cam = cams.newton
ui_filename = "cam_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class CameraControlWidget(gui.QWidget, Ui_Widget):
    spec_initialize = core.pyqtSignal()
    spec_register = core.pyqtSignal()
    cam_initialize = core.pyqtSignal()
    cam_register = core.pyqtSignal()
    cool_down = core.pyqtSignal(int)
    cooler_off = core.pyqtSignal()
    cam_shut_down = core.pyqtSignal()
    spec_shut_down = core.pyqtSignal()

    def __init__(self, event_processor, cam=None):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Enable startup with no camera connected
        if cam is None:
            return
        # Otherwise continue with __init__
        self.cam = cam
        self.spec = self.cam.spec
        self.cam_thread = core.QThread()
        core.QTimer.singleShot(0, self.cam_thread.start)
        self.cam.moveToThread(self.cam_thread)

        # Set the permanent labels
        self.titleLabel.setText(self.cam.name)
        self.serialLabel.setText(str(self.cam.serial))

        # Create status and connect the status update signal to self.update_gui
        self.state = CameraControlState(self)
        self.state.gui_update.connect(self.update_gui)

        # NOTE: DON'T NEED TO CONNECT BUTTON SIGNALS TO SELF'S SLOTS. When the
        # slots are of the format on_objectName_signalName, setupUi will
        # connect them automatically.

        # Connect self's signals to the camera's slots
        self.spec_initialize.connect(self.cam.spec.initialize)
        self.spec_register.connect(self.cam.spec.register)
        self.cam_initialize.connect(self.cam.initialize)
        self.cool_down.connect(self.cam.cooldown)
        self.cooler_off.connect(self.cam.cooler_off)
        self.cam_shut_down.connect(self.cam.shut_down)
        self.spec_shut_down.connect(self.cam.spec.shut_down)

        # Connect the restart buttons to the state's slots
        self.restartCamButton.clicked.connect(
            self.state.set_transition_shutting_down)
        self.restartAllButton.clicked.connect(
            self.state.set_transition_shutting_down)
        self.initAllButton.clicked.connect(
            self.state.set_transition_restarting)

        # Chain spec init, spec reg, and cam init
        self.spec.initialization_done.connect(self.spec.register)
        self.spec.registration_done.connect(self.cam.initialize)

        # Create restart chain
        self.spec.shutdown_done.connect(self.cam.shut_down)
        self.cam.shutdown_done.connect(self.restart)

    def on_initAllButton_clicked(self):
        self.spec_initialize.emit() # chained to spec.register and cam.init

    def on_cooldownButton_clicked(self):
        self.cool_down.emit(self.tempSpin.getValue())

    def on_coolerOffButton_clicked(self):
        self.cooler_off.emit()

    def on_restartCamButton_clicked(self):
        self.cam_shut_down.emit()

    def on_restartAllButton_clicked(self):
        self.spec_shut_down.emit()

    def restart(self):
        if self.status.spec_initialized == False:
            # Then the spectrograph was never shut down, so we only want to
            # restart the camera
            self.cam_initialize.emit()
        else:
            # Then we restart both, via a chain
            self.spec_initialize.emit()

    def update_gui(self, gui_choices, gui_statuses):
        # Enable and disable stuff
        for attr in gui_choices.__slots__:
            getattr(self, attr).setEnabled(getattr(gui_choices, attr))

        # Set label text and other parameters
        for attr in ("cameraStatusLabel", "tempLabel", "coolerLabel",
            "programStatusLabel"):
            getattr(self, attr).setText(getattr(gui_statuses, attr))

        self.tempSpin.setValue(gui_statuses.tempSpin_value)
        self.tempSpin.setRange(
            gui_statuses.tempSpin_min, gui_statuses.tempSpin_max)

    def closeEvent(self, event):
        self.cooldownButton.setEnabled(False)
        self.coolerOffButton.setEnabled(False)
        self.restartCamButton.setEnabled(False)
        self.restartAllButton.setEnabled(False)
        self.tempSpin.setEnabled(False)

        self.cam_shut_down.emit()
        self.spec_shut_down.emit()

        event.accept()

class CameraControlState(core.QObject):
    """Class for turning information about the program into GUI decisions

    This class curates up-to-date information about the state of the program
    and uses it to keep the GUI up-to-date. Through the widget that instant-
    iates it, the camera's signals are connected to its slots, and its own
    signals are connected to the widget's slots (e.g. to enable/disable
    buttons.)

    The state of the program is divided into two halves: transient states and
    permanent states.
    * Transient states are info about the GUI (and internally): when the
      "Initialize" button is pressed, the instance's transient state is set to
      "initializing". Transient states switch the behavior of the instance
      under different permanent states.
    * Permanent states are info about the camera (and internally): when the
      cooler is turned on, `cooler_status` is set to "DRV_TEMP_NOT_REACHED".
      Permanent states keep track of this info to keep the display up to date.

    This class uses a QTimer to stay up-to-date, so it may have to deal simul-
    taneously with signals sent by the camera and the timer's timeout signal.
    This raises the question of whether the class is thread-safe: might some
    attribute change in between when update is called and when it updates the
    display? The answer is: IT'S THREAD SAFE AS LONG AS THE INSTANCE IS MOVED
    TO A NEW THREAD UPON CREATION AND ALL SIGNALS ARE QUEUED. When two signals
    arrive around the same time, so that first one is accepted, blocks the
    event loop while it executes, and then quits before the second one is
    accepted.
    """
    gui_update = core.pyqtSignal(object, object)

    class GuiChoicesState(object):
        """Stores information about all the gui objects that need to be
        enabled or disabled"""
        __slots__ = (
            "initAllButton",
            "cooldownButton",
            "coolerOffButton",
            "restartCamButton",
            "restartAllButton",
            "tempSpin"
            )

    class GuiStatusState(object):
        """Stores information about all the gui objects that need to have
        certain status text/parameters synced"""
        __slots__ = (
            "cameraStatusLabel",
            "tempLabel",
            "coolerLabel",
            "programStatusLabel",
            "tempSpin_value",
            "tempSpin_max",
            "tempSpin_min",
            )

    def __init__(self, parent):
        core.QObject.__init__(self)

        self.parent = parent
        self.cam = self.parent.cam
        # Ignore spectrometer initialization; needs to be registered too first
        self.cam.spec.registration_done.connect(self.set_spec_to_initialized)
        self.cam.initialization_done.connect(self.set_cam_to_initialized)
        self.cam.cooldown_started.connect(self.set_cooler_to_on)
        self.cam.cooldown_stopped.connect(self.set_cooler_to_off)
        self.cam.shutdown_done.connect(self.set_cam_to_uninitialized)
        self.cam.spec.shutdown_done.connect(self.set_spec_to_uninitialized)
        self.cam.message.connect(self.set_program_status)

        self.spec_initialized = False
        self.cam_initialized = False
        self.cooler_on = False
        self.cam_status = "init"
        self.cooler_status = "init"
        self.temp = "init"
        self.program_status = "waiting for init"
        self.transition_state = "idling"
        self.tempSpin_value = self.tempSpin_max = self.tempSpin_min = 0
        self.tempSpin_enabled = False

        # Check for updates automatically every once in a while
        self.timer = core.QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.update()

    def update(self):
        # Create a self.GuiChoicesState struct to fill
        gui_choices = self.GuiChoicesState()

        # Switch: which transition state? => enable/disable stuff
        {
            "idling": self.update_idling,
            "shutting_down": self.update_shutting_down,
            "restarting": self.update_restarting,
            "starting_cooler": self.update_starting_cooler,
            "stopping_cooler": self.update_stopping_cooler
        }.get(self.transition_state, self.unknown_transition)(gui_choices)

        # Update the statuses stored in self and store those values in
        # another struct to be emitted with the gui update
        gui_statuses = self.GuiStatusState()
        self.update_statuses(gui_statuses)

        # Send the update to the GUI
        self.gui_update.emit(gui_choices, gui_statuses)

    def update_idling(self, gui_choices):
        if self.spec_initialized and self.cam_initialized:
            gui_choices.initAllButton = False
            gui_choices.restartCamButton = True
            gui_choices.restartAllButton = True

            # When the cooler is already on, this just changes the target temp
            gui_choices.cooldownButton = True
            gui_choices.tempSpin = True

            gui_choices.coolerOffButton = True if self.cooler_on else False

        elif not self.spec_initialized and not self.cam_initialized:
            gui_choices.initAllButton = True
            gui_choices.restartCamButton = False
            gui_choices.restartAllButton = False
            gui_choices.cooldownButton = False
            gui_choices.tempSpin = False
            gui_choices.coolerOffButton = False

        else:
            msg = "Was something disconnected? While idling, cam and spec " \
                  "were not both inited nor not-inited"
            raise Exception(msg)

    def update_shutting_down(self, gui_choices):
        """Stay busy and pass to restarting when the cam shuts down"""
        if not cam_initialized:
            self.transition_state = "restarting"
            self.update_restarting(gui_choices)
        else:
            self.update_choices_busy(gui_choices)

    def update_restarting(self, gui_choices):
        """Stay busy until cam and spec are reinitialized"""
        if self.cam_initialized and self.spec_initialized:
            self.transition_state = "idling"
            self.update_idling(gui_choices)
        else:
            self.update_choices_busy(gui_choices)

    def update_starting_cooler(self, gui_choices):
        """Stay busy until cooler is on"""
        if self.cooler_on:
            self.transition_state = "idling"
            self.update_idling(gui_choices)
        else:
            self.update_choices_busy(gui_choices)

    def update_stopping_cooler(self, gui_choices):
        """Stay busy until cooler is off"""
        if not self.cooler_on:
            self.transition_state = "idling"
            self.update_idling(gui_choices)
        else:
            self.update_choices_busy(gui_choices)

    def update_choices_busy(self, gui_choices):
        """Disable everything disableable"""
        for attr in gui_choices.__slots__:
            setattr(gui_choices, attr, False)

    def unknown_transition(self, gui_enableds):
        raise AttributeError("%r doesn't recognize transition state %r" %
            self.transition_state, self)

    def update_statuses(self, gui_statuses):
        """Update and store statuses of cam, temp, cooler, and program"""
        if self.cam_initialized and self.spec_initialized:
            # Get cam status, temp, and cooler status from camera
            self.cam_status = gui_statuses.cam_status = \
                self.parent.cam.get_status()
            self.temp, self.cooler_status = \
                gui_statuses.temp, gui_statuses.cooler_status = \
                self.parent.cam.get_temp()

        else:
            for attr in ("cam_status", "temp", "cooler_status"):
                setattr(self, attr, "init")
            for attr in ("cameraStatusLabel", "tempLabel", "coolerLabel"):
                setattr(gui_statuses, attr, "init")

        # Get the program status from self, which is informed whenever the
        # camera emits a message.
        gui_statuses.programStatusLabel = self.program_status

        # Also get the spinBox values from self
        for attr in ("tempSpin_value", "tempSpin_min", "tempSpin_max"):
            setattr(gui_statuses, attr, getattr(self, attr))

    # Setter slots for states set by signals (no alliteration intended)
    def set_spec_to_initialized(self):
        self.spec_initialized = True
        self.update()
    def set_cam_to_initialized(self):
        self.cam_initialized = True
        self.update()
    def set_cooler_to_on(self, temp):
        self.cooler_on = True
        self.tempSpin_value = temp
        self.update()
    def set_cooler_to_off(self):
        self.cooler_on = False
        self.update()
    def set_cam_to_uninitialized(self):
        self.cam_initialized = False
        self.update()
    def set_spec_to_uninitialized(self):
        self.spec_initialized = False
        self.update()
    def set_program_status(self, s):
        self.program_status = s
        self.update()
    def set_transition_shutting_down(self):
        self.transition_state = "shutting_down"
        self.update()
    def set_transition_restarting(self):
        self.transition_state = "restarting" # also initializing
        self.update()

def main(cam=default_cam):
    app = gui.QApplication(sys.argv)
    window = CameraControlWidget(app.processEvents, cam=cam)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())