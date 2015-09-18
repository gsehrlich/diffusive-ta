from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
import cam_control
import numpy as np
from contextlib import contextmanager
from andor.andorcamera import newton # for __main__ behavior
from imager import Imager
import atexit
import pyqtgraph as pg

ui_filename = "rms.ui" # filename here

# Parse the Designer .ui file 
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class RmsWidget(gui.QWidget, Ui_Widget):
    acquire = core.pyqtSignal(int)
    abort = core.pyqtSignal()

    def __init__(self, x, new_image):
        "Accepts the x-dimension of the camera and a signal that sends data."
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.imager = RmsImager(x, new_image)

        self.spinBox.valueChanged.connect(self.imager.change_n)
        self.acquire.connect(self.imager.acquire)
        self.abort.connect(self.imager.abort)

        self.rmsPlot.setMouseEnabled(x=False, y=True)
        self.curve = self.rmsPlot.plot()
        self.imager.plot.connect(self.curve.setData)

        self.n_max = 1

        #HAAAACK
        self.other_plot = pg.plot()
        self.other_plot.setMouseEnabled(x=False, y=True)
        self.other_curve = self.other_plot.plot()
        self.imager.other_plot.connect(self.other_curve.setData)

    def new_nmax(self, n_max):
        self.n_max = n_max

    def startAcq(self, default_n=10):
        self.spinBox.setMaximum(self.n_max)
        self.spinBox.setValue(min(default_n, self.n_max))
        self.acquire.emit(min(default_n, self.n_max))

    def abortAcq(self):
        self.abort.emit()

class RmsImager(Imager):
    other_plot = core.pyqtSignal(object, object)

    def acquire(self, n):
        # Set up an additional tally
        self.sum_sq = np.zeros(self.x, dtype=np.int64)

        # Pre-allocate two additional auxiliary arrays for calculation
        self.rms = np.zeros(self.x, dtype=float)
        self.percent_err = np.zeros(self.x, dtype=float)

        # Let the superclass take care of the rest
        super(RmsImager, self).acquire(n)

    def calc(self, data):
        # Progressively increase denominator of avg until n is reached
        if self.start_countup < self.n:
            i = self.next_index()
            self.start_countup += 1

            # Copy new data into empty storage
            self.storage[i] = data

            # Add data into running tallies
            self.sum += self.storage[i]
            self.sum_sq += self.storage[i]**2

            # Calculate: rms = sqrt(<x^2> - <x>^2)
            self.avg[:] = self.sum / self.start_countup
            self.rms[:] = np.sqrt(self.sum_sq/self.start_countup - self.avg**2)

        # Then just use n
        else:
            i = self.next_index()

            # Take the oldest data out of the running tally
            self.sum -= self.storage[i]
            self.sum_sq -= self.storage[i]**2

            # Copy new data over the old data
            self.storage[i] = data

            # Add data into running tallies
            self.sum += self.storage[i]
            self.sum_sq += self.storage[i]**2

            # Calculate: rms = sqrt(<x^2> - <x>^2)
            self.avg[:] = self.sum / self.n
            self.rms[:] = np.sqrt(self.sum_sq/self.n - self.avg**2)

        # Tell listeners to plot
        self.percent_err[:] = self.rms/self.avg
        self.plot.emit(xrange(self.x), self.percent_err)

        #HAAAACK
        self.other_plot.emit(xrange(self.x), self.avg)

    def abort(self):
        super(RmsImager, self).abort()
        del self.sum_sq

if __name__ == "__main__":
    app = gui.QApplication([])
    newton.initialize()
    w = RmsWidget(newton)
    w.show()
    app.exec_()