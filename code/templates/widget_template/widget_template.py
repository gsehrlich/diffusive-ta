# from http://pythonforengineers.com/your-first-gui-app-with-python-and-pyqt/

import sys
from PyQt4 import QtCore, QtGui, uic
import os.path

ui_filename = "widget_template.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class TaxCalculator(QtGui.QWidget, Ui_Widget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # connect events to methods here

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = TaxCalculator()
    window.show()
    sys.exit(app.exec_())