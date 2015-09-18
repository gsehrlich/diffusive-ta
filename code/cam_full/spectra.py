from PyQt4 import QtCore as core, QtGui as gui, uic
from imager import AvgImager

ui_filename = "spectra.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SpectraWidget(core.QObject, Ui_Widget):
    acquire = core.pyqtSignal(int)
    abort = core.pyqtSignal()

    def __init__(self, x, new_pump_probe, new_probe_only):
        core.QObject.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.imager = DifferenceImager(x, new_pump_probe, new_probe_only)

        self.imager = RmsImager(x, new_image)

        self.spinBox.valueChanged.connect(self.imager.change_n)
        self.acquire.connect(self.imager.acquire)
        self.abort.connect(self.imager.abort)

        self.diffPlot.setMouseEnabled(x=False, y=True)
        self.curve = self.diffPlot.plot()
        self.imager.plot.connect(self.curve.setData)

        self.n_max = 1

class DifferenceImager(AvgImager)