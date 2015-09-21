from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
from imager import AvgImager, ImagerWidget
import numpy as np

class DifferenceImager(AvgImager):
    def __init__(self, x, new_pump_probe, new_probe_only):
        # Initialize so that new_pump_probe activates the plotting routine
        super(DifferenceImager, self).__init__(x, new_pump_probe)
        self.new_probe_only = new_probe_only

    def set_background(self, backg):
        self.backg[:] = backg

    def acquire(self, n):
        # Create an auxiliary array for subtracting the background
        self.backg = np.zeros(self.x, dtype=float)
        self.ratio = np.zeros(self.x, dtype=float)

        # Manually connect new_probe_only to background updater
        self.new_probe_only.connect(self.set_background)

        super(DifferenceImager, self).acquire(n)

    def calc(self, data):
        self.ratio[:] = self.backg / data

        # Instead of averaging continuously over raw data, do so over back-
        # ground-corrected data.
        super(DifferenceImager, self).calc(self.ratio)

    def abort(self):
        super(DifferenceImager, self).abort()
        del self.ratio, self.backg

ui_filename = "diff.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class DifferenceWidget(ImagerWidget, Ui_Widget):
    ImagerClass = DifferenceImager
    plot_name = "diffPlot"

    def finish_setup(self):
        core.QObject.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)