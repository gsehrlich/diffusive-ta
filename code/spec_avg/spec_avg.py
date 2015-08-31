from PyQt4 import QtGui, QtCore, uic
from andor.andorcamera import idus
import numpy as np
import sys

ui_filename = "specgraphtest.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SpecGraphWidget(QtGui.QWidget, Ui_Widget):
    def __init__(self, plot_generator):
        QtGui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.go_button.clicked.connect(self.start_acquiring)

        self.plot_generator = plot_generator
        self.plot_generator.done.connect(self.release_button)

        """
        self.plot_generator.plot_image.connect(self.img)
        self.imager.getHistogramWidget().hide() # or make .close() work
        """

        self.curve = self.plotter.plot()
        self.plot_generator.plot.connect(self._plot)

    @QtCore.pyqtSlot()
    def start_acquiring(self):
        self.go_button.setEnabled(False)
        self.plot_generator.start.emit()

    @QtCore.pyqtSlot()
    def release_button(self):
        self.go_button.setEnabled(True)

    @QtCore.pyqtSlot(np.ndarray, np.ndarray)
    def _plot(self, x, y):
        global app
        y = np.random.randn(512)
        self.curve.setData(x, y)
        #app.processEvents()
        print "plotted"

    @QtCore.pyqtSlot(np.ndarray, int, int)
    def img(self, img, mx, mn):
        global app
        self.imager.setImage(img, levels=(mx, mn), autoHistogramRange=False)
        app.processEvents()

"""
class Imager(QtCore.QObject):
    start = QtCore.pyqtSignal()
    plot_image = QtCore.pyqtSignal(np.ndarray, int, int)
    done = QtCore.pyqtSignal()

    def __init__(self, n_kinetics=50):
        super(Imager, self).__init__()

        self.start.connect(self.acquire)

        self.cam_thread = QtCore.QThread()
        self.cam_thread.start()

        idus.moveToThread(self.cam_thread)
        idus.new_images.connect(self.generate)
        idus.done_acquiring.connect(self.done)
        self.alloc = np.zeros((n_kinetics, idus.x), dtype=np.int32)
        self.kinetic_args = (self.alloc,)
        self.kinetic_kwargs = {
            "n_accums": 1,
            "accum_cycle_time": 0,
            "n_kinetics": n_kinetics,
            "kin_cycle_time": 0.1,
        }

        self.images_gathered = 0

    @QtCore.pyqtSlot()
    def acquire(self):
        self.alloc[:] = 0
        self.images_gathered = 0
        idus.func_call.emit("kinetic", self.kinetic_args, self.kinetic_kwargs)

    @QtCore.pyqtSlot(int)
    def generate(self, n):
        self.images_gathered += n
        disp = self.alloc[:self.images_gathered]
        # plot everything, but base color on filled-in region
        self.plot_image.emit(self.alloc, disp.min(), disp.max())

    def __del__(self):
        "Quit thread before deletion
        self.cam_thread.terminate()
"""

class ContinuousImager(QtCore.QObject):
    start = QtCore.pyqtSignal()
    plot = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    done = QtCore.pyqtSignal()

    def __init__(self, n_avg=10):
        super(ContinuousImager, self).__init__()

        self.start.connect(self.acquire)

        self.cam_thread = QtCore.QThread()
        self.cam_thread.start()

        self.n_avg = n_avg
        self.x = np.arange(idus.x)

        idus.moveToThread(self.cam_thread)
        idus.new_images.connect(self.generate)
        idus.done_acquiring.connect(self.done)
        self.alloc = np.zeros((1, idus.x), dtype=np.int32)
        self.averager = np.zeros((self.n_avg, idus.x), dtype=np.int32)
        self.args = (self.alloc,)
        self.kwargs = {
            "n_accums": 1,
            "accum_cycle_time": 0,
            "kin_cycle_time": .1,
            "wavelen": 543
        }

    @QtCore.pyqtSlot()
    def acquire(self):
        self.alloc[:] = 0
        self.averager[:] = 0
        idus.func_call.emit("scan_until_abort", self.args, self.kwargs)

    @QtCore.pyqtSlot(int)
    def generate(self, n):
        for i in xrange(self.n_avg - 1):
            self.averager[i] = self.averager[i + 1]
        self.averager[-1] = self.alloc[0]
        disp = sum(self.averager, 0)
        self.plot.emit(self.x, self.alloc[0])
        print "emitted"

    def __del__(self):
        """Quit thread before deletion"""
        self.cam_thread.terminate()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = SpecGraphWidget(ContinuousImager())
    window.show()
    print "starting"
    sys.exit(app.exec_())