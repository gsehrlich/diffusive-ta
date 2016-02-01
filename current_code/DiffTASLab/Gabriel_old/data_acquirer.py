from __future__ import division
from PyQt4 import QtCore as core, QtGui as gui, uic
import atexit
import numpy as np
import datetime
import data_crunchers as dc

# Parse the Designer .ui file 
# Ui_Widget, QtBaseClass = uic.loadUiType("plotterWidget.ui")

# class PlotterWidget(gui.QWidget, Ui_Widget):
#     acquire = core.pyqtSignal(int)
#     abort = core.pyqtSignal()
#     n_max = 1000000 # boxcar average at most one million spectra
#     default_n = 128 # default to one hundred spectra

#     def __init__(self, PlotterClass, title, x, *signals):
#         "Accepts the x-dimension of the camera and a signal that sends data."
#         gui.QWidget.__init__(self)
#         Ui_Widget.__init__(self)
#         self.setupUi(self)

#         # Create and connect the object that will tell this widget what to plot
#         self.plotter = PlotterClass(x, *signals)
#         self.acquire.connect(self.plotter.acquire)
#         self.curve = self.plotWidget.plot()
#         self.plotter.plot.connect(self.curve.setData)
#         self.plotter.new_data_available.connect(self.update_countup)
#         self.plotter.fps.connect(self.update_fps)
#         self.abort.connect(self.plotter.abort)

#         # Set up the plot area
#         self.plotWidget.setTitle(title)
#         self.plotWidget.setMouseEnabled(x=False, y=True)

#         # Set up the boxcar width picker
#         self.boxcarWidthSpinBox.setMaximum(self.n_max)
#         self.boxcarWidthSpinBox.setValue(self.default_n)
#         self.boxcarWidthSpinBox.valueChanged.connect(self.plotter.change_n)

#     def startAcq(self):
#         self.acquire.emit(self.boxcarWidthSpinBox.value())

#     def update_countup(self, n):
#         self.countupLabel.setText(str(n))

#     def update_fps(self, fps):
#         self.fpsLabel.setText(str(fps))

#     def abortAcq(self):
#         self.abort.emit()

class DataAcquirerSpectral(core.QObject):
    #plot    = core.pyqtSignal(object, object)
    new_data_collected  = core.pyqtSignal(float, object, object, int)
    new_data_processed  = core.pyqtSignal(object)
    #fps                 = core.pyqtSignal(int)
    #acquire = core.pyqtSignal(int)
    abort               = core.pyqtSignal()
    n_max           = 1000000   # boxcar average at most one million spectra
    default_n       = 100       # default to one hundred spectra
    default_mode    = "blockwise" # default acquisition (and plotting) mode


    def __init__(self, x, new_image, mode):
        super(DataAcquirerSpectral, self).__init__()

        if mode is None:
            self.mode = self.default_mode
        else:
            self.mode = mode

        self.x = x
        self.new_image = new_image # camera signal that triggers calculation
        self.running = False
        # For fps calculation. Leave out earliest 2.5 ms
        self.one_second = datetime.timedelta(seconds=1, microseconds=-2500)

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


    def acquire(self, n):
        # Leave all array allocation beyond storage to subclasses

        # Set up counters

        self.n = n
        if mode == "blockwise":
            # blockwise readout and averaging: use twice the bufferlength
            self.buflen = self.n
        else:
            # running averager: bufferlength == boxcar
            self.buflen = self.n

        self.i_pp = -1     # First thing it does is get incremented
        self.i_po = -1     # First thing it does is get incremented
        self.countup_pp = 0
        self.countup_po = 0

        # Set up storage
        self.po_buf = dc.createAcquisitionArrays(self.x, self.buflen)   # probe-only buffer
        self.pp_buf = dc.createAcquisitionArrays(self.x, self.buflen)   # pump-probe buffer
        self.po     = dc.createAcquisitionArrays(self.x, self.n)        # probe-only signal
        self.pp     = dc.createAcquisitionArrays(self.x, self.n)        # pump-probe signal
        #self.ra     = dc.createAcquisitionArrays(self.x, self.n)        # po/pp ratio
        #self.od     = dc.createAcquisitionArrays(self.x, self.n)        # optical density

        #self.storage = np.zeros((self.n, self.x), dtype=np.int32)

        # Set up fft arrays for calculating ratio using the FFT phase method
        self.fftbuf = dc.createFFTArrays(self.x, self.n)    

        # Get ready to calculate fps
        self.plot_times = []

        # Go
        if self.mode == "blockwise":
            self.new_image.connect(self.collect_blockwise)
        else:
            self.new_image.connect(self.collect_running)
            
        self.new_data_collected.connect(self.process_data)

        self.running = True


   def collect_blockwise(self, x_arr, y_arr, is_pump_probe):
        # Progressively increase denominator of avg until n is reached
        if is_pump_probe:
            if self.i_pp < self.n:
                # Increment counters
                self.i_pp += 1
                self.countup_pp += 1
        
                # put incoming image into appropriate buffer (po or pp)
                self.pp_buf.data[:,self.i_pp] = y_arr
            else:
                # buffer length has been reached

                # copy incoming buffer to working buffer 
                self.pp.data = self.pp_buf.data
                self.pp_full = True
                self.i_pp += 1
                self.i_pp %= self.n
        else:
            # data is from probe-only
            if self.i_po < self.n:
                # Increment counters
                self.i_po += 1
                self.countup_pp += 1
        
                # put incoming image into appropriate buffer (po or pp)
                self.po_buf.data[:,self.i_po] = y_arr
            else:
                # buffer length has been reached

                # copy incoming buffer to working buffer 
                self.po.data = self.po_buf.data
                self.po_full = True
                self.i_po += 1
                self.i_po %= self.n

        if self.pp_full && self.po_full:
            # reset flags
            self.pp_full = False
            self.po_full = False
            self.countup_pp = 0
            self.countup_po = 0

            # tell data processor to start processing
            self.new_data_collected.emit(x_arr, self.po, self.pp, self.n)



    def collect_running(self, x_arr, y_arr, is_pump_probe):
        # Progressively increase denominator of avg until n is reached
        if is_pump_probe:
            if self.i_pp < self.n:
                # Increment counters
                self.i_pp += 1
                self.countup_pp += 1
        
                # put incoming image into appropriate buffer (po or pp)
                self.pp_buf.data[:,self.i_pp] = y_arr
            else:
                # buffer length has been reached
                self.i_pp += 1
                self.i_pp %= self.n

            # copy incoming buffer to working buffer 
            self.pp.data = self.pp_buf.data
                
        else:
            # data is from probe-only
            if self.i_po < self.n:
                # Increment counters
                self.i_po += 1
                self.countup_pp += 1
        
                # put incoming image into appropriate buffer (po or pp)
                self.po_buf.data[:,self.i_po] = y_arr
            else:
                # buffer length has been reached
                self.i_po += 1
                self.i_po %= self.n

            # copy incoming buffer to working buffer 
            self.po.data = self.po_buf.data
                
        if self.i_pp == self.i_po:
            # calculate stuff
            # tell data processor to start processing
            self.new_data_collected.emit(x_arr, self.po, self.pp, self.countup_pp)


    def process_data(x_arr, po, pp, n_actual):
        # process the data just taken from the collector
        _, dlen = po.data.shape
        out.x       = x_arr
        out.po      = calcAverageStddevRmsStruct(po.data, 0, dlen)
        out.pp      = calcAverageStddevRmsStruct(pp.data, 0, dlen)
        out.ra_sim  = calcAverageStddevRmsStruct(calcPumpProbeRatioSimple(po.data, pp.data),
                                                0, dlen)
        out.od_sim  = calcAverageStddevRmsStruct(calcDeltaOD(out.ra_sim.data), 
                                                0, dlen)
        out.ra_fft  = calcAverageStddevRmsStruct(calcPumpProbeRatioFFT(po.data, pp.data, self.fftbuf), 
                                                0, dlen)
        out.od_fft  = calcAverageStddevRmsStruct(calcDeltaOD(out.ra_fft.data), 
                                                0, dlen)
        out.n_actual    = n_actual
        out.fps         = self.calc_fps()
        self.new_data_processed.emit(out)

        # # Send the calculated fps
        # self.calc_fps()



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
        return len(self.plot_times)
        #self.fps.emit(len(self.plot_times))


    def abort(self):
        self.running = False
        self.new_image.disconnect(self.send_plot)

        del self.n, self.i_po, self.i_pp, self.countup_po, self.countup_pp
        del self.po_buf, self.pp_buf, self.po, self.pp
        del self.plot_times
        del self.fft_buf


    def __del__(self):
        if self.running: self.abort()
        self.thread.quit()

