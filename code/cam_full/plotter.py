from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
import atexit
import numpy as np
import datetime

# Parse the Designer .ui file 
Ui_Widget, QtBaseClass = uic.loadUiType("plotterWidget.ui")

class PlotterWidget(gui.QWidget, Ui_Widget):
    acquire = core.pyqtSignal(int)
    abort = core.pyqtSignal()
    n_max = 1000000 # boxcar average at most one million spectra
    default_n = 100 # default to one hundred spectra

    def __init__(self, PlotterClass, title, x, *signals):
        "Accepts the x-dimension of the camera and a signal that sends data."
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Create and connect the object that will tell this widget what to plot
        self.plotter = PlotterClass(x, *signals)
        self.acquire.connect(self.plotter.acquire)
        self.curve = self.plotWidget.plot()
        self.plotter.plot.connect(self.curve.setData)
        self.plotter.countup.connect(self.update_countup)
        self.plotter.fps.connect(self.update_fps)
        self.abort.connect(self.plotter.abort)

        # Set up the plot area
        self.plotWidget.setTitle(title)
        self.plotWidget.setMouseEnabled(x=False, y=True)

        # Set up the boxcar width picker
        self.boxcarWidthSpinBox.setMaximum(self.n_max)
        self.boxcarWidthSpinBox.setValue(self.default_n)
        self.boxcarWidthSpinBox.valueChanged.connect(self.plotter.change_n)

    def startAcq(self):
        self.acquire.emit(self.boxcarWidthSpinBox.value())

    def update_countup(self, n):
        self.countupLabel.setText(str(n))

    def update_fps(self, fps):
        self.fpsLabel.setText(str(fps))

    def abortAcq(self):
        self.abort.emit()

class Plotter(core.QObject):
    plot = core.pyqtSignal(object, object)
    countup = core.pyqtSignal(int)
    fps = core.pyqtSignal(int)

    def __init__(self, x, new_image):
        super(Plotter, self).__init__()

        self.x = x
        self.new_image = new_image # signal that triggers calculation
        self.running = False
        self.mode = "lin" # averaging
        self.one_second = datetime.timedelta(seconds=1) # for fps calculation

        # Give self own event loop so that incoming signals are queued
        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)

        # End safely upon exit
        atexit.register(self.__del__)

    def change_n(self, n):
        """Stop and restart with different number of averages"""
        if self.running and n != self.n:
            # Restart with new value of n
            self.abort()
            self.acquire(n)

    def change_mode(self, mode):
        if mode not in ("lin", "log"):
            raise TypeError("Mode %r not recognized" % mode)
        elif mode != self.mode:
            n = self.n
            self.abort()
            self.mode = mode
            self.acquire(n)

    def index_generator(self):
        """Return a generator that loops through the active rows"""
        i = 0
        while True:
            yield self.active_rows[i]
            i += 1
            i %= len(self.active_rows)

    def acquire(self, n):
        # Set up counters
        self.n = n
        self.active_rows = range(self.n)
        self.next_index = self.index_generator().next # this fn gets next index
        self.start_countup = 0

        # Set up storage and tallies.
        # Use float for generality, including when mode == "log"
        self.storage = np.zeros((n, self.x), dtype=float)
        self.sum = np.zeros(self.x, dtype=float)

        # Pre-allocate auxiliary array for calculation
        self.avg = np.zeros(self.x, dtype=float)

        # Get ready to calculate fps
        self.plot_times = []

        # Go
        self.new_image.connect(self.calc)
        self.new_image.connect(self.calc_fps)
        self.running = True

    def calc(self, x_arr, y_arr):
        """Must implement this method in subclasses."""
        # Qt complains when I use an abstract base class, so do this instead:
        raise NotImplementedError

    def calc_fps(self):
        now = datetime.datetime.now()
        one_second_ago = now - self.one_second
        self.plot_times.append(now)

        for i in xrange(len(self.plot_times)):
            # look for where one second ago starts
            if self.plot_times[i] > one_second_ago:
                # get rid of everything before that and quit
                del self.plot_times[:i]
                break
        self.fps.emit(len(self.plot_times))

    def abort(self):
        self.running = False
        self.new_image.disconnect(self.calc)
        self.new_image.disconnect(self.calc_fps)

        del self.n, self.active_rows, self.next_index, self.start_countup
        del self.sum, self.storage, self.avg
        del self.plot_times

    def __del__(self):
        if self.running: self.abort()
        self.thread.quit()

class AvgPlotter(Plotter):
    def calc(self, x_arr, y_arr):
        if self.mode == "log":
            y_arr = np.log(y_arr)

        # Progressively increase denominator of avg until n is reached
        if self.start_countup < self.n:
            i = self.next_index()
            self.start_countup += 1

            # Copy new y_arr into empty storage
            self.storage[i] = y_arr

            # Add y_arr into running tally
            self.sum += self.storage[i]

            # Calculate and store avg
            self.avg[:] = self.sum / self.start_countup

        # Then just use n
        else:
            i = self.next_index()

            # Take the oldest y_arr out of the running tally
            self.sum -= self.storage[i]

            # Copy new y_arr over the old y_arr
            self.storage[i] = y_arr

            # Add y_arr into running tally
            self.sum += self.storage[i]

            # Calculate avg
            self.avg[:] = self.sum / self.n

        self.plot.emit(x_arr, self.avg)
        if self.start_countup <= self.n: self.countup.emit(self.start_countup)