# from http://pythonforengineers.com/your-first-gui-app-with-python-and-pyqt/

import sys
from PyQt4 import QtCore, QtGui, uic
import sync
import time

ui_filename = "chopper.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class ChopperControls(QtGui.QWidget, Ui_Widget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Set internal state at the beginning
        self.chopper_is_on = False
        self.freq = 100.
        self.editing = False

        # Connect widgets to methods
        self.on_button.clicked.connect(self.turn_chopper_on)
        self.off_button.clicked.connect(self.turn_chopper_off)
        self.freq_edit.returnPressed.connect(self.update_freq)
        self.freq_edit.textEdited.connect(self.text_edited)
        self.freq_edit.editingFinished.connect(self.editing_finished)

        # Create daemon to synchronize display with internal state
        # We'll start it after the window is shown
        self.sync_daemon = sync.SyncDaemon()

        # We will sync button states to internal on/off state
        sync_vals = [
            (self.is_chopper_on, self.on_button.isChecked, 
                self.on_button.setChecked),
            (self.is_chopper_off, self.off_button.isChecked,
                self.off_button.setChecked)
            ]
        # We'll also sync the text in the lineEdit to the internal freq state
        sync_vals.extend([
            (self.get_freq_str, self.freq_edit.text, self.set_freq_edit_text)
            ])

        # Sync everything
        for sync_val in sync_vals:
            self.sync_daemon.sync(*sync_val)

    # Start synchronizing
    def show(self):
        QtGui.QWidget.show(self)
        self.sync_daemon.start()

    #######
    # GETTERS AND SETTERS
    #######

    def is_chopper_on(self):
        return self.chopper_is_on

    def is_chopper_off(self):
        return not self.chopper_is_on

    def parse_lineEdit_freq(self):
        """
        try:
            val = float(self.freq_edit.text())
        except e:
            freq_edit.paletteChange(QtGui.QPalette(base=(255, 128, 128)))
        """
        return float(self.freq_edit.text())

    def get_freq_str(self):
        return "%.3g" % self.freq

    #####
    # FUNCTIONS CONNECTED TO WIDGETS
    #####

    def turn_chopper_on(self):
        self.chopper_is_on = True
        self.status_label.setText("Chopper turned on")

    def turn_chopper_off(self):
        self.chopper_is_on = False
        self.status_label.setText("Chopper turned off")

    def update_freq(self):
        self.freq = self.parse_lineEdit_freq()
        self.status_label.setText("Freq set to %s" % self.get_freq_str())

    def text_edited(self):
        self.editing = True

    def editing_finished(self):
        self.editing = False

    #####
    # OTHER FUNCTIONS?
    #####

    # this function isn't "connect"ed to a widget
    def set_freq_edit_text(self, s):
        if not self.editing:
            self.freq_edit.setText(s)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = ChopperControls()
    window.show()
    sys.exit(app.exec_())