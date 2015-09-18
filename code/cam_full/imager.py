from PyQt4 import QtCore as core, QtGui as gui
import atexit
import numpy as np

"""
class ImagerWidget(gui.QWidget):
    acquire = core.pyqtSignal(int)
    abort = core.pyqtSignal()
    ImagerClass = Imager
    plot_name = NotImplemented # Need to provide name of PlotWidget attribute

    def __init__(self, x, *signals):
        "Accepts the x-dimension of the camera and a signal that sends data."
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.imager = ImagerClass(x, *signals)

        self.spinBox.valueChanged.connect(self.imager.change_n)
        self.acquire.connect(self.imager.acquire)
        self.abort.connect(self.imager.abort)

        getattr(self, plot_name).setMouseEnabled(x=False, y=True)
        self.curve = self.rmsPlot.plot()
        self.imager.plot.connect(self.curve.setData)

        self.n_max = 1

    def new_nmax(self, n_max):
        self.n_max = n_max

    def startAcq(self, default_n=10):
        self.spinBox.setMaximum(self.n_max)
        self.spinBox.setValue(min(default_n, self.n_max))
        self.acquire.emit(min(default_n, self.n_max))

    def abortAcq(self):
        self.abort.emit()
"""

class Imager(core.QObject):
    plot = core.pyqtSignal(object, object)

    def __init__(self, x, new_image):
        super(Imager, self).__init__()

        self.x = x
        self.new_image = new_image
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
            # Restart with new value of n
            self.abort()
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

        # Set up storage and tallies
        self.storage = np.zeros((n, self.x), dtype=np.int32)
        self.sum = np.zeros(self.x, dtype=np.int64) # lots of 32-bit ints added

        # Pre-allocate auxiliary array for calculation
        self.avg = np.zeros(self.x, dtype=float)

        # Go
        self.new_image.connect(self.calc)
        self.running = True

    def calc(self, new_data):
        """Must implement this method in subclasses."""
        raise NotImplementedError

    def abort(self):
        self.running = False
        self.new_image.disconnect(self.calc)

        del self.n, self.active_rows, self.next_index, self.start_countup
        del self.sum, self.storage

    def __del__(self):
        if self.running: self.abort()
        self.thread.quit()

class AvgImager(Imager):
    def calc(self, data):
        # Progressively increase denominator of avg until n is reached
        if self.start_countup < self.n:
            i = self.next_index()
            self.start_countup += 1

            # Copy new data into empty storage
            self.storage[i] = data

            # Add data into running tally
            self.sum += self.storage[i]

            # Calculate and store avg
            self.avg[:] = self.sum / self.start_countup


        # Then just use n
        else:
            i = self.next_index()

            # Take the oldest data out of the running tally
            self.sum -= self.storage[i]

            # Copy new data over the old data
            self.storage[i] = data

            # Add data into running tallies
            self.sum += self.storage[i]

            # Calculate avg
            self.avg[:] = self.sum / self.n

        self.plot.emit(avg)