import sys
from PyQt4 import QtCore, QtGui, uic
# implicitly use pyqtgraph
import numpy as np
import time
from andor.andorcamera import idus

ui_filename = "specgraphtest.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SpecGraphWidget(QtGui.QWidget, Ui_Widget):
    def __init__(self, plot_generator, style="img"):
        QtGui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.imager.getHistogramWidget().hide() # or make .close() work

        self.plot_generator = plot_generator
        self.go_button.clicked.connect(self.start_acquiring)
        self.plot_generator.plot_image.connect(self.img)
        self.plot_generator.done.connect(self.release_button)

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
        self.curve.setData(x, y)
        app.processEvents()

    @QtCore.pyqtSlot(np.ndarray, int, int)
    def img(self, img, mx, mn):
        global app
        self.imager.setImage(img, levels=(mx, mn), autoHistogramRange=False)
        app.processEvents()

# Out-of-date: make them emit signals into thin air that SpecGraphWidget hears
"""
class PlotGenerator(QtCore.QObject):
    def __init__(self, plotter, dt=10):
        super(PlotGenerator, self).__init__()

        self.plotter = plotter
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.generate)
        self.timer.start(dt)

    @QtCore.pyqtSlot()
    def generate(self): pass

class Waver(PlotGenerator):
    def __init__(self, plotter):
        super(Waver, self).__init__(plotter)

        self.x = np.arange(1000)/1000.*np.pi
        self.i = 0

    @QtCore.pyqtSlot()
    def generate(self):
        self.plotter.plot.emit(self.x, np.sin(self.x - 0.01*self.i))
        self.i += 1
        print self.i

class RandomImager(PlotGenerator):
    @QtCore.pyqtSlot()
    def generate(self):
        self.plotter.img.emit(np.random.randn(5, 5))
"""

class KineticImager(QtCore.QObject):
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
        """Quit thread before deletion"""
        self.cam_thread.terminate()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = SpecGraphWidget(KineticImager())
    window.show()
    print "starting"
    sys.exit(app.exec_())