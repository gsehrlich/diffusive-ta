import sys
from PyQt4 import QtGui, QtCore, uic
from chopper_copy import ChopperControls
from delaystage import DelayStageWidget
from ThorlabsBeamshutter import BeamshutterWidget

from MeasurementItem import DataViewer

# debug
import time, datetime

class TestMain(DataViewer):
    def __init__(self):
        super(TestMain, self).__init__(parent=None)
        self.init_UI()

    def init_UI(self):
        self.resize(800, 800)
        self.devices = {}

        self.chopper = self.addWidget("Optical Chopper", ChopperControls())
        self.delaystage = self.addWidget("Delay stage", DelayStageWidget(),
            minSize=(250,250))
        self.shutter = self.addWidget("Beamshutter", BeamshutterWidget(),
            position="right", relativeTo="Delay stage", minSize=(250,250))

    def add_device(self, name=None, device=None):
        if name in devices:
            raise Key


def main():
    app = QtGui.QApplication(sys.argv)

    w = TestMain()
    w.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()