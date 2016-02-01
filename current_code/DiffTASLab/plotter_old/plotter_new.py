from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
import atexit
import numpy as np
import pyfftw as fftw
import datetime
from data_acquirer import DataAcquirer

# Parse the Designer .ui file 
Ui_Widget, QtBaseClass = uic.loadUiType("plotterWidget.ui")

class PlotterWidget(gui.QWidget, Ui_Widget):
    acquire = core.pyqtSignal(int)
    abort = core.pyqtSignal()
    n_max = 1000000 # boxcar average at most one million spectra
    default_n = 128 # default to one hundred spectra

    def __init__(self, PlotterClass, title, x, *signals):
        "Accepts the x-dimension of the camera and a signal that sends data."
        gui.QWidget.__init__(self)
        Ui_Widget.__init__(self)
        self.setupUi(self)

        # Create and connect the object that will tell this widget what to plot
        self.plotter = PlotterClass(x, *signals)
        #self.data_acquirer = 
        self.acquire.connect(self.plotter.acquire)
        #self.acquire.connect(self.plotter.acquire)
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
    plot    = core.pyqtSignal(object, object)
    countup = core.pyqtSignal(int)
    fps     = core.pyqtSignal(int)

    def __init__(self, x, new_image):
        super(Plotter, self).__init__()

        self.acquirer = DataAcquirer(x, new_image, "running")
        self.acquirer.new_data_processed.connect(self.send_plot)
        # self.x = x
        # self.new_image = new_image # camera signal that triggers calculation
        # self.running = False
        # # For fps calculation. Leave out earliest 2.5 ms
        # self.one_second = datetime.timedelta(seconds=1, microseconds=-2500)


        # # Give self own event loop so that incoming signals are queued
        # self.thread = core.QThread()
        # self.moveToThread(self.thread)
        # core.QTimer.singleShot(0, self.thread.start)

        # End safely upon exit
        atexit.register(self.__del__)

    def change_n(self, n):
        """Stop and restart with different number of averages"""
        if self.running and n != self.n:
            # Restart with new value of n
            self.abort()
            self.acquire(n)

    def acquire(self, n):
        # Leave all array allocation beyond storage to subclasses

        # Set up counters
        # self.n = n
        # self.i = -1     # First thing it does is get incremented
        # self.start_countup = 0

        # # Set up storage
        # self.storage = np.zeros((self.n, self.x), dtype=np.int32)

        # # Set up fft arrays
        # self.ft_in = fftw.n_byte_align(np.zeros((n, self.x), dtype=np.complex128), 16)
        # self.ft_out = fftw.n_byte_align(np.zeros((n, self.x), dtype=np.complex128), 16)
        # self.ift_in = fftw.n_byte_align(np.zeros((n, self.x), dtype=np.complex128), 16)
        # self.ift_out = fftw.n_byte_align(np.zeros((n, self.x), dtype=np.complex128), 16)
        # self.high_pass = np.zeros((n, self.x), dtype=np.complex128)
        # self.high_pass[0,:] = 1
        # self.fft = fftw.FFTW(self.ft_in, self.ft_out, axes=(0,), direction='FFTW_FORWARD',
        #                     flags=('FFTW_MEASURE',), threads=1, planning_timelimit=None)
        # self.ifft = fftw.FFTW(self.ift_in, self.ift_out, axes=(0,), direction='FFTW_BACKWARD',
        #                     flags=('FFTW_MEASURE',), threads=1, planning_timelimit=None)
        # # self.fft = fftw.FFTW(self.ft_in, self.ft_out, axes=(0), direction='FFTW_FORWARD')
        # # self.ifft = fftw.FFTW(self.ift_in, self.ift_out, axes=(0), direction='FFTW_BACKWARD')
        

        # # Get ready to calculate fps
        # self.plot_times = []

        # Go
        #self.new_image.connect(self.send_plot)
        
        self.acquirer.acquire(n)
        self.running = True


    def send_plot(self, datablock):
        # Tell listeners to plot what self.calc returns
        self.plot.emit(self.x, datablock.ra_sim.average)

        
    # def send_plot(self, x_arr, y_arr):
    #     # Progressively increase denominator of avg until n is reached
    #     if self.start_countup < self.n:
    #         # Increment counters
    #         self.i += 1
    #         self.start_countup += 1

    #         # Tell listeners to plot what self.countup_calc returns
    #         self.plot.emit(*self.countup_calc(x_arr, y_arr))

    #         # Tell listeners how far in the start countup self is
    #         self.countup.emit(self.start_countup)
    #     # Then just use n
    #     else:
    #         # Increment rotating counter only, modulus len(storage)
    #         self.i += 1
    #         self.i %= self.n

    #         # Tell listeners to plot what self.calc returns
    #         self.plot.emit(*self.calc(x_arr, y_arr))

    #     # Send the calculated fps
    #     self.calc_fps()

    #     # Afterwards, save the new data into storage (over any old data)
    #     self.storage[self.i] = y_arr

    def countup_calc(self, x_arr, y_arr):
        """By default, just call calc"""
        return self.calc(x_arr, y_arr)

    def calc(self, x_arr, y_arr):
        """Must implement this method in subclasses."""
        # Qt complains when I use an abstract base class, so do this instead:
        raise NotImplementedError

    def calc_fps(self):
        now = datetime.datetime.now()
        one_second_ago = now - self.one_second
        self.plot_times.append(now)

        for j in xrange(len(self.plot_times)):
            # look for where one second ago starts
            if self.plot_times[j] > one_second_ago:
                # get rid of everything before that and quit
                del self.plot_times[:j]
                break
        self.fps.emit(len(self.plot_times))

    def abort(self):
        self.running = False
        self.new_image.disconnect(self.send_plot)

        del self.n, self.i, self.start_countup
        del self.storage
        del self.plot_times
        del self.ft_in, self.ft_out, self.ift_in, self.ift_out
        del self.fft, self.ifft, self.high_pass

    def __del__(self):
        if self.running: self.abort()
        self.thread.quit()

class AvgPlotter(Plotter):
    def acquire(self, n):
        # Set up tally
        self.sum = np.zeros(self.x, dtype=np.int64)

        # Pre-allocate auxiliary array for calculation
        self.avg = np.zeros(self.x, dtype=float)

        super(AvgPlotter, self).acquire(n)

    # def countup_calc(self, x_arr, y_arr):
    #     # Add y_arr into running tally
    #     self.sum += y_arr

    #     # Calculate and return avg. This is true_division
    #     self.avg[:] = self.sum / self.start_countup
    #     return x_arr, self.avg
    def countup_calc(self, x_arr, y_arr):
        return self.countup_calc_fft(x_arr, y_arr)

    def countup_calc_fft(self, x_arr, y_arr):
        # perform fft, high-pass filter and ifft for probe signal
        self.PROBE = self.fft(self.storage)
        self.avg = self.ifft(self.PROBE * self.high_pass)[0,:].real
        
        return x_arr, self.avg

    def calc(self, x_arr, y_arr):
        # Take the oldest y_arr out of the running tally
        self.sum -= self.storage[self.i]

        # Then just do the same as during countup
        #return self.countup_calc(x_arr, y_arr)
        return self.countup_calc_fft(x_arr, y_arr)

    def abort(self):
        super(AvgPlotter, self).abort()
        del self.sum, self.avg
        del self.PROBE

class RmsPlotter(Plotter):
    def acquire(self, n):
        # Set up tallies
        self.sum = np.zeros(self.x, dtype=np.int64)
        self.sum_sq = np.zeros(self.x, dtype=np.int64)

        # Pre-allocate auxiliary arrays for calculation
        self.avg = np.zeros(self.x, dtype=float)
        self.rms = np.zeros(self.x, dtype=float)
        self.percent_err = np.zeros(self.x, dtype=float)

        # Let the superclass take care of the rest
        super(RmsPlotter, self).acquire(n)

    def countup_calc(self, x_arr, y_arr):
        # Add y_arr into running tallies
        self.sum += y_arr
        self.sum_sq += y_arr**2

        # Calculate: rms = sqrt(<x^2> - <x>^2). This is true_divide
        self.avg[:] = self.sum / self.start_countup
        self.rms[:] = np.sqrt(self.sum_sq/self.start_countup - self.avg**2)
        self.percent_err[:] = self.rms / self.avg
        return x_arr, self.percent_err

    def calc(self, x_arr, y_arr):
        # Take the oldest y_arr out of the running tallies
        self.sum -= self.storage[self.i]
        self.sum_sq -= self.storage[self.i]**2

        # Then just do the same as during countup
        return self.countup_calc(x_arr, y_arr)

    def abort(self):
        super(RmsPlotter, self).abort()
        del self.sum_sq, self.rms, self.percent_err

class RatioPlotter(Plotter):
    def __init__(self, x, new_probe_only, new_pump_probe):
        # Initialize so that new_probe_only activates the plotting routine
        super(RatioPlotter, self).__init__(x, new_probe_only)
        self.new_pump_probe = new_pump_probe

    def set_pump_probe(self, x_arr, pump_probe):
        self.recent_pump_probe[:] = pump_probe

    def acquire(self, n):
        # Create storage and tallies. Use superclass-created self.storage for
        # probe_only data.
        self.recent_pump_probe = np.zeros(self.x, dtype=np.int32)
        self.pump_probe_storage = np.zeros((n, self.x), dtype=np.int32)
        self.pump_probe_sum = np.zeros(self.x, dtype=np.int64)
        self.probe_only_sum = np.zeros(self.x, dtype=np.int64)
                
        # Create auxiliary array for calculating ratio
        self.ratio = np.zeros(self.x, dtype=float)

        # Manually connect the signal Plotter doesn't automatically connect
        self.new_pump_probe.connect(self.set_pump_probe)

        super(RatioPlotter, self).acquire(n)

    def send_plot(self, x_arr, probe_only):
        super(RatioPlotter, self).send_plot(x_arr, probe_only)

        # Also copy pump_probe into empty storage
        self.pump_probe_storage[self.i] = self.recent_pump_probe

    # def countup_calc(self, x_arr, probe_only):
    #     # Add arrays into running tallies
    #     self.pump_probe_sum += self.recent_pump_probe
    #     self.probe_only_sum += probe_only

    #     # Calculate and return the ratio. This is true_division
    #     self.ratio[:] = self.probe_only_sum / self.pump_probe_sum
    #     return x_arr, self.ratio

    def countup_calc(self, x_arr, y_arr):
        return self.countup_calc_fft(x_arr, y_arr)

    def countup_calc_fft(self, x_arr, probe_only):
        # perform fft, high-pass filter and ifft for probe and pump-probe signals
        self.PROBE = self.fft(self.storage)
        self.probe_only_sum = self.ifft(self.PROBE * self.high_pass)[0,:].real
        self.PUMP = self.fft(self.pump_probe_storage_diff)
        self.pump_probe_sum = self.ifft(self.PUMP * self.high_pass)[0,:].real

        # Calculate and return the ratio. This is true_division
        self.ratio[:] = self.probe_only_sum / self.pump_probe_sum
        #print(str(self.ratio.size))
        return x_arr, self.ratio

    def calc(self, x_arr, probe_only):
        # Take the oldest arrays out of the running tallies
        self.pump_probe_sum -= self.pump_probe_storage[self.i]
        self.probe_only_sum -= self.storage[self.i]

        # shift pump-probe by half a period
        self.pump_probe_diff = np.diff(self.pump_probe_storage, axis=0)
        self.pump_probe_storage_diff = self.pump_probe_storage + 0.5 * np.concatenate((self.pump_probe_diff[:,:],[self.pump_probe_diff[-1,:]]),axis=0)
        self.pump_probe_storage_diff = np.concatenate(([self.pump_probe_storage_diff[0,:]], self.pump_probe_storage_diff[0:-1,:]),axis=0)
        # Then just do the same as during countup
        #return self.countup_calc(x_arr, probe_only)
        return self.countup_calc_fft(x_arr, probe_only)

    def abort(self):
        super(RatioPlotter, self).abort()

        # Manually disconnect the signal Plotter doesn't automatically
        # disocnnect
        self.new_pump_probe.disconnect(self.set_pump_probe)
        del self.recent_pump_probe, self.pump_probe_storage
        del self.pump_probe_sum, self.probe_only_sum
        del self.ratio
        del self.PROBE, self.PUMP
        del self.pump_probe_diff, self.pump_probe_storage_diff
