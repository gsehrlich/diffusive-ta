from PyQt4 import QtCore as core, QtGui as gui, uic
import andor.andorcamera as cams
from andor._known import cam_info
import sys
from contextlib import contextmanager
import time

default_cam = cams.newton
ui_filename = "cam_control.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class CameraControlWidget(gui.QWidget, Ui_Widget):
    get_ready_to_close = core.pyqtSignal()

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
        self.cam_controller_thread = core.QThread()
        self.cam_controller.moveToThread(self.cam_controller_thread)
        self.cam_controller_thread.started.connect(
            self.cam_controller.make_timer)
        core.QTimer.singleShot(0, self.cam_controller_thread.start)

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

    def place_status_placeholders(self):
        for label in (self.cameraStatusLabel,
                      self.tempLabel,
                      self.coolerLabel,
                      self.programStatusLabel):
            label.setText("init?")

    def update_program_status(self, s):
        # Show only most recent line of status
        if len(self.program_status) > 0 and self.program_status[-1] == "\n":
            self.program_status = ""
        self.program_status += s
        self.programStatusLabel.setText(str(self.program_status).strip())

    def set_enabled(self, widget, val):
        widget.setEnabled(val)

    def set_text(self, widget, text):
        widget.setText(text)

    def set_tempSpin_value_range(self, val, mn, mx):
        self.tempSpin.setRange(mn, mx)
        self.tempSpin.setValue(val)

    def closeEvent(self, event):
        """Close the camera only when it's ready"""
        if self.ready_to_close:
            event.accept()
        else:  
            self.get_ready_to_close.emit()
            event.ignore()

    def finish_closing(self):
        self.cam_controller_thread.exit()
        self.ready_to_close = True
        self.close()

class CameraController(core.QObject):
    spec_initialize = core.pyqtSignal()
    spec_register = core.pyqtSignal()
    cam_initialize = core.pyqtSignal()
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
        self.cam_thread = core.QThread()
        self.cam.moveToThread(self.cam_thread)
        self.cam.spec.moveToThread(self.cam_thread)
        core.QTimer.singleShot(0, self.cam_thread.start)

        self.all_buttons = (
            self.widget.initAllButton,
            self.widget.cooldownButton,
            self.widget.coolerOffButton,
            self.widget.restartCamButton,
            self.widget.restartAllButton
            )

        # Connect signals to the camera's slots
        self.spec_initialize.connect(self.cam.spec.initialize,
            type=core.Qt.BlockingQueuedConnection)
        self.spec_register.connect(self.cam.spec.register,
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
        # Make this timer fast so that it will probably catch disconnection
        # errors before the user's clicks do
        self.status_timer.setInterval(10)
        self.status_timer.timeout.connect(self.update_camera_status_temp)

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
        status = self.cam.get_status()
        temp, cooler_status = self.cam.get_temp()
        self.set_text.emit(self.widget.cameraStatusLabel, status)
        self.set_text.emit(self.widget.tempLabel, str(temp))
        self.set_text.emit(self.widget.coolerLabel, cooler_status)

    def init_spec(self):
        self.spec_initialize.emit()
        self.spec_register.emit()

    def init_cam(self):
        # Initalize the camera
        self.cam_initialize.emit()

        # Set allowed temp range and default, then enable
        self.set_tempSpin_value_range.emit(cam_info[self.cam.name]["temp"],
            *self.cam.get_temp_range())
        self.set_enabled.emit(self.widget.tempSpin, True)

        # Start checking the camera status
        self.status_timer.start()

    def shut_down_cam(self):
        time.sleep(2)
        self.status_timer.stop()
        self.cooler_off.emit()
        self.update_camera_status_temp()
        self.cam_shut_down.emit()

    def shut_down_spec(self):
        self.spec_shut_down.emit()

    def close(self):
        self.set_enabled.emit(self.widget.cooldownButton, False)
        self.set_enabled.emit(self.widget.coolerOffButton, False)
        self.set_enabled.emit(self.widget.restartCamButton, False)
        self.set_enabled.emit(self.widget.restartAllButton, False)
        self.set_enabled.emit(self.widget.tempSpin, False)

        if self.cam.is_initialized(): self.shut_down_cam()
        if self.cam.spec.is_initialized(): self.shut_down_spec()
        self.cam_thread.exit()

        self.done_closing.emit()

    # currently unused
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
    """

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

#currently unused
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
    app = gui.QApplication(sys.argv)
    window = CameraControlWidget(cam=cam)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())