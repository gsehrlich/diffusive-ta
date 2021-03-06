# Gabriel Ehrlich
# gabriel.s.ehrlich@gmail.com
# 28 September 2015

"""Defines a widget for initializing and cooling down Andor cameras

This module defines two interacting classes to control the GUI.
- CameraControlWidget takes care of GUI-thread stuff. The buttons in the
    GUI are attributes of it, so it's the responsibility of the widget
    to dispatch these signals appropriately.
- CameraController takes care of the actual work. So that the main
    thread, which contains the GUI, can stay responsive to user input,
    the widget dispatches instructions to this object to take care of
    one at a time. This object blocks its containing thread while wait-
    ing for the camera to initialize, not the GUI thread.
"""

from PyQt4 import QtCore as core, QtGui as gui, uic
import andor.andorcamera as cams
from andor._known import cam_info
import sys
from contextlib import contextmanager
import time
import atexit

default_cam = cams.newton
ui_filename = "cam_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class CameraControlWidget(gui.QWidget, Ui_Widget):
    """Controls GUI elements and dispatches events/signals."""
    get_ready_to_close = core.pyqtSignal()
    cam_initialize_done = core.pyqtSignal(bool) # First arg: acquiring
    cam_shut_down = core.pyqtSignal()

    def __init__(self, cam=None):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Enable startup with no camera connected
        if cam is None:
            return
        else:
            self.cam = cam

        self.cam_controller = CameraController(self, self.cam)

        # Connect self's button's signals to functions in self's
        # controller, not self
        self.initAllButton.clicked.connect(
            self.cam_controller.on_initAllButton_clicked)
        self.cooldownButton.clicked.connect(
            self.cam_controller.on_cooldownButton_clicked)
        self.coolerOffButton.clicked.connect(
            self.cam_controller.on_coolerOffButton_clicked)
        self.restartCamButton.clicked.connect(
            self.cam_controller.on_restartCamButton_clicked)
        self.restartAllButton.clicked.connect(
            self.cam_controller.on_restartAllButton_clicked)

        # Set the labels that won't change
        self.titleLabel.setText(self.cam.name)
        self.serialLabel.setText(str(self.cam.serial))
        self.place_status_placeholders()

        # Prepare to display cam/spec messages
        self.program_status = ""
        self.cam.message.connect(self.update_program_status)
        self.cam.spec.message.connect(self.update_program_status)

        # Prepare to receive GUI instructions from controller
        self.cam_controller.set_enabled.connect(self.set_enabled,
            type=core.Qt.BlockingQueuedConnection)
        self.cam_controller.set_text.connect(self.set_text,
            type=core.Qt.BlockingQueuedConnection)
        self.cam_controller.set_tempSpin_value_range.connect(
            self.set_tempSpin_value_range,
            type=core.Qt.BlockingQueuedConnection)

        # Deal with window closing
        self.get_ready_to_close.connect(self.cam_controller.close)
        self.cam_controller.done_closing.connect(self.finish_closing)
        self.ready_to_close = False

        # Tell listeners when the cam is started or shut down
        self.cam_controller.cam_initialize_done.connect(
            self.cam_initialize_done)
        self.cam_controller.cam_shut_down.connect(self.cam_shut_down)

    def place_status_placeholders(self):
        """Tell user that statuses will updated upon initialization"""
        for label in (self.cameraStatusLabel,
                      self.tempLabel,
                      self.coolerLabel,
                      self.programStatusLabel):
            label.setText("init?")

    def update_program_status(self, s):
        """Show user the most recent message from the camera object"""
        # Show only most recent line of status
        if len(self.program_status) > 0 and self.program_status[-1] == "\n":
            self.program_status = ""
        self.program_status += s
        self.programStatusLabel.setText(str(self.program_status).strip())

    def set_enabled(self, widget, val):
        """Slot for controller's set_text signal"""
        widget.setEnabled(val)

    def set_text(self, widget, text):
        """Slot for controller's set_enabled signal"""
        widget.setText(text)

    def set_tempSpin_value_range(self, val, mn, mx):
        """Slot for controller's set_tempSpin_value_range signal"""
        self.tempSpin.setRange(mn, mx)
        self.tempSpin.setValue(val)

    def closeEvent(self, event):
        """Close the camera only when it's ready"""
        if self.ready_to_close:
            event.accept()
        else:
            event.ignore()
            self.get_ready_to_close.emit()

    def finish_closing(self):
        """Slot for controller's done_closing signal"""
        self.ready_to_close = True
        # implicitly call self.closeEvent again now that self is ready
        self.close()

class CameraController(core.QObject):
    """Sends instructions to the camera/spectro and monitors them"""
    spec_initialize = core.pyqtSignal()
    cam_initialize = core.pyqtSignal()
    cam_initialize_done = core.pyqtSignal(bool) # first arg: acquiring
    cool_down = core.pyqtSignal(int)
    cooler_off = core.pyqtSignal()
    cam_shut_down = core.pyqtSignal()
    spec_shut_down = core.pyqtSignal()
    done_closing = core.pyqtSignal()
    set_enabled = core.pyqtSignal(gui.QWidget, bool)
    set_text = core.pyqtSignal(gui.QWidget, str)
    set_tempSpin_value_range = core.pyqtSignal(int, int, int)

    def __init__(self, widget, cam):
        core.QObject.__init__(self)

        self.widget = widget
        self.cam = cam

        self.all_buttons = (
            self.widget.initAllButton,
            self.widget.cooldownButton,
            self.widget.coolerOffButton,
            self.widget.restartCamButton,
            self.widget.restartAllButton
            )

        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)
        self.thread.started.connect(self.make_timer)
        self.running = False
        atexit.register(self.close)

        # Connect signals to the camera's slots
        self.spec_initialize.connect(self.cam.spec.initialize,
            type=core.Qt.BlockingQueuedConnection)
        self.cam_initialize.connect(self.cam.initialize,
            type=core.Qt.BlockingQueuedConnection)
        self.cool_down.connect(self.cam.cooldown,
            type=core.Qt.BlockingQueuedConnection)
        self.cooler_off.connect(self.cam.cooler_off,
            type=core.Qt.BlockingQueuedConnection)
        self.cam_shut_down.connect(self.cam.shut_down,
            type=core.Qt.BlockingQueuedConnection)
        self.spec_shut_down.connect(self.cam.spec.shut_down,
            type=core.Qt.BlockingQueuedConnection)

    def make_timer(self):
        """Wait until after __init__ to make timer so it's in new thread"""
        # Create and connect a timer to update the camera status etc.
        self.status_timer = core.QTimer()
        self.status_timer.setInterval(16)
        self.status_timer.timeout.connect(self.update_camera_status_temp)

        # Also keep track of whether self.close has been called yet
        self.running = True

    def on_initAllButton_clicked(self):
        self.set_enabled.emit(self.widget.initAllButton, False)
        with self.all_buttons_disabled():
            # Initialize and reigster the spectrometer
            self.init_spec()

            # Do all the cam initialization stuff
            self.init_cam()

        # Enable relevant buttons that were disabled on startup
        self.set_enabled.emit(self.widget.cooldownButton, True)
        self.set_enabled.emit(self.widget.restartCamButton, True)
        self.set_enabled.emit(self.widget.restartAllButton, True)

    def on_cooldownButton_clicked(self):
        with self.all_buttons_disabled():
            self.cool_down.emit(self.widget.tempSpin.value())

        # Allow the user to turn off the cooler
        self.set_enabled.emit(self.widget.coolerOffButton, True)

    def on_coolerOffButton_clicked(self):
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        with self.all_buttons_disabled():
            self.cooler_off.emit()

    def on_restartCamButton_clicked(self):
        self.set_enabled.emit(self.widget.cooldownButton, False)
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        self.set_enabled.emit(self.widget.restartCamButton, False)
        self.set_enabled.emit(self.widget.restartAllButton, False)
        self.set_enabled.emit(self.widget.tempSpin, False)

        self.shut_down_cam()
        self.init_cam()

        self.set_enabled.emit(self.widget.cooldownButton, True)
        self.set_enabled.emit(self.widget.restartCamButton, True)
        self.set_enabled.emit(self.widget.restartAllButton, True)

    def on_restartAllButton_clicked(self):
        self.set_enabled.emit(self.widget.cooldownButton, False)
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        self.set_enabled.emit(self.widget.restartCamButton, False)
        self.set_enabled.emit(self.widget.restartAllButton, False)
        self.set_enabled.emit(self.widget.tempSpin, False)

        self.shut_down_cam()
        self.shut_down_spec()
        self.init_spec()
        self.init_cam()

        self.set_enabled.emit(self.widget.cooldownButton, True)
        self.set_enabled.emit(self.widget.restartCamButton, True)
        self.set_enabled.emit(self.widget.restartAllButton, True)

    def update_camera_status_temp(self):
        """Tell the widget the camera status and temp to display"""
        status = self.cam.get_status()
        self.set_text.emit(self.widget.cameraStatusLabel, status)

        if "ACQUIRING" in status and self.cam.name == "idus":
            self.set_text.emit(self.widget.tempLabel, "unknown")
            self.set_text.emit(self.widget.coolerLabel,
                "idus can't check temp right now")
        else:
            temp, cooler_status = self.cam.get_temp()
            self.set_text.emit(self.widget.tempLabel, str(temp))
            self.set_text.emit(self.widget.coolerLabel, cooler_status)

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

    def shut_down_cam(self):
        time.sleep(2)
        self.status_timer.stop()
        self.cooler_off.emit()
        self.update_camera_status_temp()
        self.cam_shut_down.emit()

    def shut_down_spec(self):
        self.spec_shut_down.emit()

    def close(self):
        """If the camera/spectro were ever initialized, shut down"""
        if self.running:
            self.set_enabled.emit(self.widget.cooldownButton, False)
            self.set_enabled.emit(self.widget.coolerOffButton, False)
            self.set_enabled.emit(self.widget.restartCamButton, False)
            self.set_enabled.emit(self.widget.restartAllButton, False)
            self.set_enabled.emit(self.widget.tempSpin, False)

            if self.cam.is_initialized(): self.shut_down_cam()
            if self.cam.spec.is_initialized(): self.shut_down_spec()

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
        print "__del__ has been called"
        if self.running: self.close()

    # The following code is unused. This is one half-started attempt to
    # handle errors raised within this thread's event loop more
    # carefully.
    """
        def careful_call(self, func, args, kwargs):
            "Deal with communication errors when calling cam functions"
            #Usage:
            #    try: return_val = careful_call(...)
            #    except: pass
            #    else:
            #        ...
            try:
                ret = func(*args, **kwargs)
            except IOError as e:
                if "SHAMROCK_COMMUNICATION_ERROR" in e.message:
                    raise
                    self.spec_comm_error()
                if "DRV_ERROR_ACK" in e.message:
                    raise
                    self.cam_comm_error()
            else:
                return ret

    def spec_comm_error(self):
        self.set_text.emit(self.widget.cameraStatusLabel, "Spec comm error")
        self.set_enabled.emit(self.widget.cooldownButton, False)
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        self.set_enabled.emit(self.widget.restartCamButton, False)
        self.set_enabled.emit(self.widget.restartAllButton, True)

    def cam_comm_error(self):
        self.set_text.emit(self.widget.cameraStatusLabel, "Cam comm error")
        self.set_text.emit(self.tempLabel, "error")
        self.set_text.emit(self.coolerLabel, "DRV_ERROR_ACK")
        self.set_enabled.emit(self.widget.cooldownButton, False)
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        self.set_enabled.emit(self.widget.restartCamButton, True)
        self.set_enabled.emit(self.widget.restartAllButton, True)
    """

# The following code is unused. This is the second half-started attempt
# to handle errors raised within event loops more carefully.
"""
class CarefulQThread(core.QThread):
    spec_comm_error = core.pyqtSignal()
    cam_comm_error = core.pyqtSignal()

    def __init__(self):
        core.QThread.__init__(self)
        self.event_loop = CarefulQEventLoop()
        self.event_loop.moveToThread(self)
        self.event_loop.spec_comm_error.connect(self.spec_comm_error)
        self.event_loop.cam_comm_error.connect(self.cam_comm_error)

    def run(self):
        self.event_loop.exec_()

class CarefulQEventLoop(core.QEventLoop):
    spec_comm_error = core.pyqtSignal()
    cam_comm_error = core.pyqtSignal()

    def processEvents(self, flags, maximumTime=None):
        try:
            if maximumTime is None:
                core.QEventLoop.processEvents(flags)
            else:
                core.QEventLoop.processEvents(flags, maximumTime)
        except IOError as e:
            if "SHAMROCK_COMMUNICATION_ERROR" in e.message:
                self.spec_comm_error.emit()
            elif "DRV_ERROR_ACK" in e.message:
                self.cam_comm_error.emit()
            else:
                raise
"""

def main(cam=default_cam):
    """Start up cam_control by itself"""
    app = gui.QApplication(sys.argv)
    window = CameraControlWidget(cam=cam)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())