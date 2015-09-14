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

    def __init__(self, cam=None):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.cam_controller = CameraController(self, cam)
        self.cam_controller_thread = core.QThread()
        self.QTimer.singleShot(0, self.cam_controller_thread.start)
        self.cam_controller.moveToThread(self.cam_controller_thread)

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

class CameraController(core.QObject):
    spec_initialize = core.pyqtSignal()
    spec_register = core.pyqtSignal()
    cam_initialize = core.pyqtSignal()
    cool_down = core.pyqtSignal(int)
    cooler_off = core.pyqtSignal()
    cam_shut_down = core.pyqtSignal()
    spec_shut_down = core.pyqtSignal()

    def __init__(self, widget, cam):
        self.widget = widget
        self.cam = cam

        # Enable startup with no camera connected
        if cam is None:
            return
        else:
            self.cam = cam

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
        self.cam_register.connect(self.cam.register,
            type=core.Qt.BlockingQueuedConnection)
        self.cool_down.connect(self.cam.cooldown,
            type=core.Qt.BlockingQueuedConnection)
        self.cooler_off.connect(self.cam.cooler_off,
            type=core.Qt.BlockingQueuedConnection)
        self.cam_shut_down.connect(self.cam.shut_down,
            type=core.Qt.BlockingQueuedConnection)
        self.spec_shut_down.connect(self.cam.spec.shut_down,
            type=core.Qt.BlockingQueuedConnection)

        # Create and connect a timer to update the camera status etc.
        self.status_timer = core.QTimer()
        self.status_timer.setInterval(100)
        self.status_timer.timeout.connect(self.update_camera_status)
        self.status_timer.timeout.connect(self.update_camera_temp)

        # Display cam/spec messages
        self.program_status = ""
        self.cam.message.connect(self.update_program_status)
        self.spec.message.connect(self.update_program_status)


    def on_initAllButton_clicked(self):
        self.widget.initAllButton.setEnabled(False)
        with self.all_buttons_disabled():
            # Initialize and reigster the spectrometer
            self.init_spec()

            # Do all the cam initialization stuff
            self.init_cam()

        # Enable relevant buttons that were disabled on startup
        self.widget.cooldownButton.setEnabled(True)
        self.widget.restartCamButton.setEnabled(True)
        self.widget.restartAllButton.setEnabled(True)

    def on_cooldownButton_clicked(self):
        with self.all_buttons_disabled():
            self.cool_down.emit(self.widget.tempSpin.getValue())
            self.update_camera_temp()

        # Allow the user to turn off the cooler
        self.widget.coolerOffButton.setEnabled(True)

    def on_coolerOffButton_clicked(self):
        self.widget.coolerOffButton.setEnabled(False)
        with self.all_buttons_disabled():
            self.cooler_off.emit()
            self.update_camera_temp()

    def on_restartCamButton_clicked(self):
        self.widget.cooldownButton.setEnabled(False)
        self.widget.coolerOffButton.setEnabled(False)
        self.widget.restartCamButton.setEnabled(False)
        self.widget.restartAllButton.setEnabled(False)
        self.widget.tempSpin.setEnabled(False)

        self.shut_down_cam()
        self.init_cam()

        self.widget.cooldownButton.setEnabled(True)
        self.widget.restartCamButton.setEnabled(True)
        self.widget.restartAllButton.setEnabled(True)

    def on_restartAllButton_clicked(self):
        self.widget.cooldownButton.setEnabled(False)
        self.widget.coolerOffButton.setEnabled(False)
        self.widget.restartCamButton.setEnabled(False)
        self.widget.restartAllButton.setEnabled(False)
        self.widget.tempSpin.setEnabled(False)

        self.shut_down_cam()
        self.shut_down_spec()
        self.init_spec()
        self.init_cam()

        self.widget.cooldownButton.setEnabled(True)
        self.widget.restartCamButton.setEnabled(True)
        self.widget.restartAllButton.setEnabled(True)

    def place_status_placeholders(self):
        for label in (self.widget.cameraStatusLabel,
                      self.widget.tempLabel,
                      self.widget.coolerLabel,
                      self.widget.programStatusLabel):
            label.setText("init?")

    def update_camera_status(self):
        self.widget.cameraStatusLabel.setText(self.cam.get_status())

    def update_camera_temp(self):
        temp, cooler_status = cam.get_temp()
        self.widget.tempLabel.setText(str(temp))
        self.widget.coolerLabel.setText(cooler_status)

    def update_program_status(self, s):
        # Show only most recent line of status
        if self.program_status[-1] = "\n":
            self.program_status = ""
        self.program_status += s
        self.widget.programStatusLabel.setText(self.program_status)

    def init_spec(self):
        self.spec_initialize.emit()
        self.spec_register.emit()

    def init_cam(self):
        # Initalize the camera
        self.cam_initialize.emit()

        # Set allowed temp range and default, then enable
        self.widget.tempSpin.setRange(self.cam.get_temp_range())
        self.widget.tempSpin.setValue(cam_info[cam.name]["temp"])
        self.widget.tempSpin.setEnabled(True)

        # Start checking the camera status
        self.status_timer.start()

    def shut_down_cam(self):
        self.status_timer.stop()
        self.cooler_off.emit()
        self.update_camera_temp()
        self.cam_shut_down.emit()
        self.place_status_placeholders()

    def shut_down_spec(self):
        self.spec_shut_down.emit()

    def closeEvent(self, event):
        self.widget.cooldownButton.setEnabled(False)
        self.widget.coolerOffButton.setEnabled(False)
        self.widget.restartCamButton.setEnabled(False)
        self.widget.restartAllButton.setEnabled(False)
        self.widget.tempSpin.setEnabled(False)

        self.cam_shut_down.emit()
        self.spec_shut_down.emit()

        event.accept()

    @contextmanager
    def all_buttons_disabled(self):
        """Enable or disable all buttons"""
        buttons_prev_enabled = []
        for button in self.all_buttons:
            if button.isEnabled():
                buttons_prev_enabled.append(button)
                button.setEnabled(False)

        yield

        for button in buttons_prev_enabled:
            button.setEnabled(True)

def main(cam=default_cam):
    app = gui.QApplication(sys.argv)
    window = CameraControlWidget(cam=cam)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())