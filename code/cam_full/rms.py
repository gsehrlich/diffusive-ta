from PyQt4 import QtCore as core, QtGui as gui, uic
import cam_control
import numpy as np
from contextlib import contextmanager
from andor.andorcamera import newton # for __main__ behavior
import atexit

ui_filename = "rms.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class RmsWidget(gui.QWidget, Ui_Widget):
    acquire = core.pyqtSignal(int, int, np.ndarray)
    abort = core.pyqtSignal()

    def __init__(self, cam):
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.cam = cam
        self.imager = RmsImager(self.cam.x, self.cam.new_images)

        self.spinBox.valueChanged.connect(self.imager.change_n)
        self.acquire.connect(self.imager.acquire)
        self.abort.connect(self.imager.abort)

        self.curve = self.rmsPlot.plot()
        self.imager.plot.connect(self.curve.setData)

        self.n_max = 1

    def new_nmax(self, n_max):
        self.n_max = n_max

    def startAcq(self, data, default_n=10):
        self.spinBox.setMaximum(self.n_max)
        self.spinBox.setValue(min(default_n, self.n_max))
        self.acquire.emit(min(default_n, self.n_max), self.n_max, data)

    def abortAcq(self):
        self.abort.emit()

class RmsImager(core.QObject):
    plot = core.pyqtSignal(object, object)

    def __init__(self, x, new_img_signal):
        super(RmsImager, self).__init__()

        self.x = x
        self.new_img_signal = new_img_signal
        self.running = False

        # Give self own event loop so that incoming signals are queued
        self.thread = core.QThread()
        self.moveToThread(self.thread)
        core.QTimer.singleShot(0, self.thread.start)

        # End safely upon exit
        atexit.register(self.__del__)

    def change_n(self, n):
        """Stop and restart with different number of averages"""
        if self.running and n != self.n:
            # Keep important info before aborting
            n_max = len(self.storage)
            data_ref = self.data_ref
            self.abort()

            # Restart with new value of n
            self.acquire(n, n_max, data_ref)

    def index_generator(self):
        """Return a generator that loops through the active rows"""
        i = 0
        while True:
            yield self.active_rows[i]
            i += 1
            i %= len(self.active_rows)

    def acquire(self, n, n_max, data):
        # Set up counters
        self.n = n
        self.active_rows = range(self.n)
        self.next_index = self.index_generator().next # this fn gets next index
        self.start_countup = 1

        # Set up external reference, storage, and tallies
        self.data_ref = data
        self.storage = np.zeros((n_max, self.x), dtype=np.int32)
        self.sum = np.zeros(self.x, dtype=np.int32)
        self.sum_sq = np.zeros(self.x, dtype=np.int32)

        # Go
        self.new_img_signal.connect(self.calc)
        self.running = True

    def calc(self, n_new):
        # Progressively increase denominator of avg until n is reached
        if self.start_countup <= self.n:
            i = self.next_index()

            # Copy new data into empty storage
            self.storage[i] = self.data_ref[0]

            # Add data into running tallies
            self.sum += self.storage[i]
            self.sum_sq += self.storage[i]**2

            # Calculate: rms = sqrt(<x^2> - <x>^2)
            avg = self.sum / self.start_countup
            rms = np.sqrt(self.sum_sq/self.start_countup - avg**2)

            self.start_countup += 1

        # Then just use n
        else:
            i = self.next_index()

            # Take the oldest data out of the running tally
            self.sum -= self.storage[i]
            self.sum_sq -= self.storage[i]**2

            # Copy new data over the old data
            self.storage[i] = self.data_ref[0]

            # Add data into running tallies
            self.sum += self.storage[i]
            self.sum_sq += self.storage[i]**2

            # Calculate: rms = sqrt(<x^2> - <x>^2)
            avg = self.sum / self.start_countup
            rms = np.sqrt(self.sum_sq/self.start_countup - avg**2)

        # Tell listeners to plot
        self.plot.emit(xrange(self.x), rms)

    def abort(self):
        self.running = False
        self.cam.new_img_signal.disconnect(self.calc)

        del self.n, self.active_rows, self.next_index, self.start_countup
        del self.data_ref, self.sum, self.sum_sq, self.storage

    def __del__(self):
        if self.running: self.abort()
        self.thread.quit()

if __name__ == "__main__":
    app = gui.QApplication([])
    newton.initialize()
    w = RmsWidget(newton)
    w.show()
    app.exec_()