from PyQt4 import QtGui, QtCore, uic
from andor.andorcamera import newton
import numpy as np
import sys

cam=newton

ui_filename = "specgraphtest.ui" # filename here

# Parse the Designer .ui file
Ui_Widget, QtBaseClass = uic.loadUiType(ui_filename)

class SpecGraphWidget(QtGui.QWidget, Ui_Widget):
    processEvents = QtCore.pyqtSignal()

    def __init__(self, plot_generator):
        QtGui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        self.go_button.clicked.connect(self.start_acquiring)
        self.abort_button.clicked.connect(self.abort_acquisition)
        self.abort_button.setEnabled(False)

        self.plot_generator = plot_generator

        """
        self.plot_generator.plot_image.connect(self.img)
        self.imager.getHistogramWidget().hide() # or make .close() work
        """

        self.curve = self.plotter.plot()
        self.plot_generator.plot.connect(self._plot)
        self.ready_to_plot = True

    @QtCore.pyqtSlot()
    def start_acquiring(self):
        self.go_button.setEnabled(False)
        self.plot_generator.start.emit()
        self.abort_button.setEnabled(True)

    @QtCore.pyqtSlot()
    def abort_acquisition(self):
        self.abort_button.setEnabled(False)
        self.plot_generator.abort_acq()
        self.go_button.setEnabled(True)

    @QtCore.pyqtSlot(np.ndarray, np.ndarray)
    def _plot(self, x, y):
        # check if the plotter is locked; if so, skip this curve
        if self.ready_to_plot:
            global app
            self.ready_to_plot = False
            self.curve.setData(x, y)
            self.processEvents.emit()
            self.ready_to_plot = True
        else: return

    @QtCore.pyqtSlot(np.ndarray, int, int)
    def img(self, img, mx, mn):
        global app
        self.imager.setImage(img, levels=(mx, mn), autoHistogramRange=False)
        app.processEvents()

    def closeEvent(self, event):
        self.plot_generator.quit_gracefully()
        event.accept()


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

        cam.moveToThread(self.cam_thread)
        cam.new_images.connect(self.generate)
        cam.done_acquiring.connect(self.done)
        self.alloc = np.zeros((n_kinetics, cam.x), dtype=np.int32)
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
        cam.func_call.emit("kinetic", self.kinetic_args, self.kinetic_kwargs)

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
    abort = QtCore.pyqtSignal()

    def __init__(self, cam, n_avg=1000):
        super(ContinuousImager, self).__init__()

        self.start.connect(self.acquire)

        self.cam = cam
        self.cam_thread = QtCore.QThread()

        self.n_avg = n_avg
        self.x = np.arange(self.cam.x)

        self.cam.moveToThread(self.cam_thread)
        self.cam.new_images.connect(self.generate)
        self.abort.connect(self.cam.abort,
            type=QtCore.Qt.BlockingQueuedConnection)
        self.cam_thread.start()

        self.alloc = np.zeros((1, self.cam.x), dtype=np.int32)
        self.averager = np.zeros((self.n_avg, self.cam.x), dtype=np.int32)
        self.tot = np.zeros((self.cam.x,), dtype=float)
        self.args = (self.alloc,)
        self.kwargs = {
            "kin_cycle_time": 0,
            "wavelen": 543
        }

    @QtCore.pyqtSlot()
    def acquire(self):
        self.tot[:] = 0
        self.averager[:] = 0
        self.current_ptr = 0
        self.start_countup = 0 # progressively increase n_avg until given limit
        self.cam.func_call.emit("scan_until_abort", self.args, self.kwargs)

    @QtCore.pyqtSlot(int)
    def generate(self, n_new):
        if self.start_countup < self.n_avg:
            self.averager[self.current_ptr] = self.alloc[0]
            self.tot += self.averager[self.current_ptr]
            self.current_ptr += 1
            self.current_ptr %= self.n_avg # Only matters the last time
            self.start_countup += 1
            disp = self.tot / self.start_countup
        else:
            self.tot -= self.averager[self.current_ptr]
            self.averager[self.current_ptr] = self.alloc[0]
            self.tot += self.averager[self.current_ptr]
            self.current_ptr += 1
            self.current_ptr %= self.n_avg
            disp = self.tot / self.n_avg
        self.plot.emit(self.x, disp)

    def abort_acq(self):
        # wait for acquisition to finish aborting
        # TODO: timeout and throw error
        print "aborting..."
        self.abort.emit()
        print "aborted"

    def quit_gracefully(self):
        """Quit thread before deletion"""
        self.abort_acq()
        self.cam_thread.exit()
        self.cam.shut_down()

def main(cam=cam):
    cam.spec.initialize()
    cam.spec.register()
    cam.initialize()
    cam.register()
    cam.cooldown()
    app = QtGui.QApplication(sys.argv)
    window = SpecGraphWidget(ContinuousImager(cam))
    window.processEvents.connect(app.processEvents)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())