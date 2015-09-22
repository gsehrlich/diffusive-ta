from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
from plotter import AvgPlotter, PlotterWidget
import numpy as np

class RatioPlotter(AvgPlotter):
    def __init__(self, x, new_probe_only, new_pump_probe):
        # Initialize so that new_probe_only activates the plotting routine
        super(RatioPlotter, self).__init__(x, new_probe_only)
        self.new_pump_probe = new_pump_probe

    def set_pump_probe(self, x_arr, pump_probe):
        self.pump_probe[:] = pump_probe

    def acquire(self, n):
        # Create an auxiliary array for subtracting the background
        self.pump_probe = np.zeros(self.x, dtype=float)
        self.ratio = np.zeros(self.x, dtype=float)

        # Manually connect the signal AvgPlotter doesn't automatically connect
        self.new_pump_probe.connect(self.set_pump_probe)

        super(RatioPlotter, self).acquire(n)

    def calc(self, x_arr, probe_only):
        if (self.pump_probe == 0).all():
            print "RatioPlotter is waiting for a nonzero pump-probe"
            return # wait until a pump-probe has been delivered
        self.ratio[:] = probe_only / self.pump_probe

        # Instead of averaging continuously over raw data, do so over ratio
        super(RatioPlotter, self).calc(x_arr, self.ratio)

    def abort(self):
        super(RatioPlotter, self).abort()
        self.new_pump_probe.disconnect(self.set_pump_probe)
        del self.ratio, self.pump_probe