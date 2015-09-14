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

    def __init__(self, cam=None):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Enable startup with no camera connected
        if cam is None:
            return
        else:
            self.cam = cam

        self.all_buttons = (
            self.initAllButton,
            self.cooldownButton,
            self.coolerOffButton,
            self.restartCamButton,
            self.restartAllButton
            )
        self.all_status_labels = (
            self.cameraStatusLabel,
            self.tempLabel,
            self.coolerLabel,
            self.programStatusLabel
            )

        # Set the labels
        self.titleLabel.setText(self.cam.name)
        self.serialLabel.setText(str(self.cam.serial))
        self.place_status_placeholders()

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


    def on_initAllButton_clicked(self):
        self.initAllButton.setEnabled(False)
        with self.all_buttons_disabled():
            # Initialize and reigster the spectrometer
            self.init_spec()

            # Do all the cam initialization stuff
            self.init_cam()

        # Enable relevant buttons that were disabled on startup
        self.cooldownButton.setEnabled(True)
        self.restartCamButton.setEnabled(True)
        self.restartAllButton.setEnabled(True)

    def on_cooldownButton_clicked(self):
        with self.all_buttons_disabled():
            self.cool_down.emit(self.tempSpin.getValue())
            self.update_camera_temp()

        # Allow the user to turn off the cooler
        self.coolerOffButton.setEnabled(True)

    def on_coolerOffButton_clicked(self):
        self.coolerOffButton.setEnabled(False)
        with self.all_buttons_disabled():
            self.cooler_off.emit()
            self.update_camera_temp()

    def on_restartCamButton_clicked(self):
        self.cooldownButton.setEnabled(False)
        self.coolerOffButton.setEnabled(False)
        self.restartCamButton.setEnabled(False)
        self.restartAllButton.setEnabled(False)
        self.tempSpin.setEnabled(False)

        self.shut_down_cam()
        self.init_cam()

        self.cooldownButton.setEnabled(True)
        self.restartCamButton.setEnabled(True)
        self.restartAllButton.setEnabled(True)

    def on_restartAllButton_clicked(self):
        self.cooldownButton.setEnabled(False)
        self.coolerOffButton.setEnabled(False)
        self.restartCamButton.setEnabled(False)
        self.restartAllButton.setEnabled(False)
        self.tempSpin.setEnabled(False)

        self.shut_down_cam()
        self.shut_down_spec()
        self.init_spec()
        self.init_cam()

        self.cooldownButton.setEnabled(True)
        self.restartCamButton.setEnabled(True)
        self.restartAllButton.setEnabled(True)

    def place_status_placeholders(self):
        for label in (self.cameraStatusLabel,
                      self.tempLabel,
                      self.coolerLabel,
                      self.programStatusLabel):
            label.setText("waiting for init")

    def update_camera_status(self):
        self.cameraStatusLabel.setText(self.cam.get_status())

    def update_camera_temp(self):
        temp, cooler_status = cam.get_temp()
        self.tempLabel.setText(str(temp))
        self.coolerLabel.setText(cooler_status)

    def init_spec(self):
        self.spec_initialize.emit()
        self.spec_register.emit()

    def init_cam(self):
        # Initalize and reigster the camera
        self.cam_initialize.emit()
        self.cam_register.emit()

        # Set allowed temp range and default, then enable
        self.tempSpin.setRange(self.cam.get_temp_range())
        self.tempSpin.setValue(cam_info[cam.name]["temp"])
        self.tempSpin.setEnabled(True)

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
        self.cooldownButton.setEnabled(False)
        self.coolerOffButton.setEnabled(False)
        self.restartCamButton.setEnabled(False)
        self.restartAllButton.setEnabled(False)
        self.tempSpin.setEnabled(False)

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