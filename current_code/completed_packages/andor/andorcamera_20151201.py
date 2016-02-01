"""Integrates functionality for interacting with Andor Cameras

WARNING: not thread-safe with two simultaneous cameras. May not raise errors;
may just yield garbage data.

Defines a class, `AndorCamera`, and two instances of it, `Newton01` and `iDus01`,
which bundle functionality from the andordll module for easy use from within
Python.

"""

from __future__ import print_function, division
import time
import threading
import numpy as np
from .andordll import cam_lib
from .andorspectro import Shamrock01
from ._known import cameras, cam_info
from ._q_andor_object import QAndorObject
from ctypes import c_int, byref
from PyQt4 import QtCore
from contextlib import contextmanager

class RepeatedTimer(threading.Thread):
    def __init__(self, interval, function, args=[], kwargs={}):
        super(RepeatedTimer, self).__init__()
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.running = True
        while self.running:
            self.function(*self.args, **self.kwargs)
            time.sleep(self.interval/1000)

    def stop(self):
        self.running = False

class WrappedQTimer(QtCore.QTimer):
    def __init__(self, interval, function, args=[], kwargs={}):
        super(WrappedQTimer, self).__init__()
        self.setInterval(interval)
        self.timeout.connect(lambda: function(*args, **kwargs))

def product(l):
    """Return the product of the elements in the iterable"""
    return reduce(lambda x, y: x*y, l)

class AndorCamera(object):
    "Control Andor cameras attached to a USB-controlled Andor Shamrock"
    # Allow for overriding in subclass. Must have signature
    # __init__(dt, func, args, kwargs). Must implement start() and stop().
    TimerClass = RepeatedTimer

    # temp must be an int
    default_temp = {
        "Newton01": -70,
        "iDus01": -70
        }
    acq_modes = {
        "single": 1,
        "accum:": 2,
        "kinetic": 3,
        "scan_until_abort": 5
        }
    trigger_modes = {
        "internal": 0,
        "external": 1,
        "external start": 6,
        }
    read_modes = {
        "fullbin": 0,
        "image": 4
        }

    @property
    def out(self):
        """Define out as a property with the standard getter"""
        return self._out
    @out.setter
    def out(self, val):
        """When `out` is changed, change it in cam_lib too"""
        cam_lib.out = val
        self._out = val

    def is_initialized(self, handle=None):
        """Return True if the handle is already initialized, else False.

        If no handle provided, check if the instance has a handle yet. If so,
        return True, else return False."""
        if handle is None:
            if not hasattr(self, "handle"):
                return False
            else:
                handle = self.handle

        # Set handle as current
        self.out("Setting camera with handle %r as current:" % handle,
            end=" ")
        cam_lib.SetCurrentCamera(handle)

        try:
            # Check if this camera is initialized yet
            cam_lib.GetCameraSerialNumber(str)
        except IOError as e:
            if "NOT_INITIALIZED" in e.message:
                # Camera not currently initialized
                return False
            else:
                # This shouldn't happen; that function only throws one error
                raise
        else:
            # If no error was raised, camera is already inited. Raise error
            return True

    def get_handle_dict(self, keep_serials_open=()):
        """Return a dict of serial numbers: handles.

        Warning: all cameras that were not already initialized will be
        initialized and then shut down (unless told to keep them open)."""
        # NO EASY WAY TO STORE THIS DICT AFTER MAKING IT ONCE. Handles may
        # change randomly when the cameras are not initialized, so need to
        # check each time.

        # Initialize the empty dict and begin looping through all the cameras
        self.out("Finding camera handles of all serial numbers...")
        handle_dict = {}
        for i in xrange(cam_lib.GetAvailableCameras(int)):
            # Get the handle
            handle = cam_lib.GetCameraHandle(i, int)

            # Set handle to current and find out whether it's initialized yet
            was_preinitialized = self.is_initialized(handle)

            # If not, initialize it
            if not was_preinitialized:
                self.out("Initializing:", end=" ")
                cam_lib.Initialize()

            # Find and store the serial number
            serial = cam_lib.GetCameraSerialNumber(int)
            handle_dict[serial] = handle
            self.out("Found handle %r for serial %r" % (handle, serial))

            # If the camera wasn't already inited, and the function wasn't
            # instructed to keep it open, close it.
            if not was_preinitialized and serial not in keep_serials_open:
                self.out("Shutting down serial %r" % serial, end=" ")
                cam_lib.ShutDown()

        # Store this in the class and then return it
        return handle_dict
    
    def make_current(self, out=True):
        """Make sure cam_lib knows this is the current camera

        If handle is not defined yet, self.__getattr__ will raise a good error.
        """
        if cam_lib.GetCurrentCamera(int) != self.handle:
            if out: self.out("Making %s current:" % self.name,)
            cam_lib.SetCurrentCamera(self.handle)
            
    def __init__(self, serial, spec, out=print):
        """Set up attributes for AndorCamera instance

        `out` should be a function that accepts *args and a kwargs 'sep', with
        the intention of printing them somewhere."""
        # Initialize this as a QtCore.QObject so that it can have bound signals
        super(AndorCamera, self).__init__()

        # Store the serial number of the desired camera, and get the name
        self.serial = serial
        self.name = cameras[self.serial]

        # Tell the camera and spectrometer they've been attached
        self.spec = spec
        self.spec.attached_cameras.add(self)

        # Store the passed out function (implicitly updating cam_lib)
        # and update `spec` with it too
        self.out = out
        self.spec.out = out

    def initialize(self):
        #print("init" + self.name + "\n")
        
        """Initialize the Andor DLL wrapped by this object"""
        if self.is_initialized():
            raise Exception("%r already inited!" % self.name)
        # Try handle corresponding to index given in cam_info
        ind = cam_info[self.name]["index"]
        handle = cam_lib.GetCameraHandle(ind, int)

        # Set handle as current and find out whether it's initialized yet
        was_preinitialized = self.is_initialized(handle)
        if not was_preinitialized:
            # If not, initialize it
            self.out("Initializing %r:" % self.name, end=" ")
            cam_lib.Initialize()

        # Check if the serial number is right
        serial = cam_lib.GetCameraSerialNumber(int)
        if self.serial == serial:
            # If it's right, set the handle
            self.handle = handle
        else:
            # Otherwise, look up all the handles' serial numbers to find
            # the correct one, and store it. This will keep the right one open.
            # Also keep the wrong one open until after this loop.
            self.out("Wrong serial number %r. Should be %r." % 
                (serial, self.serial), end=" ")
            handle_dict = self.get_handle_dict(keep_serials_open=(self.serial,))
            self.handle = handle_dict[self.serial]

            # Then shut down the one that's wrong.
            if not was_preinitialized:
                self.out("Setting wrong camera with handle %r as current:" % 
                        handle, end=" ")
                cam_lib.SetCurrentCamera(handle)
                self.out("Shutting down wrong camera:", end=" ")
                cam_lib.ShutDown()

        # Set up detector size information
        self.make_current()
        x, y = cam_lib.GetDetector(int, int)
        self.x = long(x)
        self.y = long(y)
        self.img_dims = {
            "image": (self.y, self.x),
            "fullbin": (self.x,)
            }
        self.x_width, self.y_width = cam_lib.GetPixelSize(float, float)

    def __getattr__(self, name):
        """Throw comprehensible error if camera is not yet initialized.

        This function will only be called if the attribute is not found through
        the usual means (e.g. the object __dict__ and all class and superclass
        __dict__s)."""
        # Create standard message
        message = "%r object has no attribute %r" % (type(self), name)
        # If it's one of the attribute names defined in initialize,
        # add additional explanation.
        if name in ("handle", "x", "y", "img_dims"):
            message += ". Must call .initialize() first"

        raise AttributeError(message)

    def cooldown(self, temp=None):
        """Start the camera cooldown"""
        self.make_current()
        # Fetch the target temperature and then set it
        if temp is None:
            temp = int(cam_info[self.name]["temp"])
        else:
            temp = int(temp)
        self.out("Setting temp to %d:" % temp, end=" ")
        cam_lib.SetTemperature(temp)

        # Start the cooldown
        # If no temperatue provided, will use whatever default the lib/cam has
        self.out("Turning cooler on:", end=" ")
        cam_lib.CoolerON()

    def get_temp_range(self):
        """Return the (min, max) temperature of the camera"""
        self.make_current()
        return cam_lib.GetTemperatureRange(int, int)
        
    def get_temp(self, out=False):
        """Return the camera's current temp (not goal temp) and cooler status"""
        self.make_current()
        temp = c_int()
        # don't want usual return behavior, so go to ctypes.cdll object
        ret = cam_lib.lib.GetTemperature(byref(temp))
        if out:
            self.out("\r\t%d, %s" % (temp.value, cam_lib.errs[ret]))
        return temp.value, cam_lib.errs[ret]
        
    def wait_until_cool(self, out=False, dt=5):
        """Do nothing until the camera is stabilized at the goal temp"""
        self.make_current()

        stabilized = False
        if out:
            self.out("Waiting for temp to reach %d" % self.temp)
            self.out("Temp is: ")
        while not stabilized:
            temp, status = self.get_temp(out=out)
            if status == "DRV_TEMPERATURE_STABILIZED":
                stabilized = True
            # Wait dt seconds in between checking whether it's stabilized
            if not stabilized: time.sleep(dt)
                
    def get_status(self):
        """Get the camera's status"""
        self.make_current()
        return cam_lib.errs[cam_lib.GetStatus(int)]

    def assert_idle(self):
        """Make sure the camera is idle; if not, raise AssertionError"""
        assert self.get_status() == "DRV_IDLE"

    def patient_assert_idle(self, dt=1, out=False):
        """Give the camera a little extra time to become idle if necessary"""
        try:
            self.assert_idle()
        except AssertionError:
            if out:
                self.out("Waiting an extra %g seconds for idle..." % dt)
            time.sleep(dt)
            self.assert_idle()        
        
    def prep_acquisition(self, acq_mode, read_mode, exp_time=0,
                         accum_cycle_time=None, n_accums=None,
                         kin_cycle_time=None, n_kinetics=None,
                         trigger="external", keep_clean_mode="wait",
                         slit=None, wavelen=None):
        """Set parameters for image acquisition

        Required parameters:
            Acquisition mode:
                Single-scan: 1
                Accumulate: 2
                Kinetics: 3
                Fast Kinetics: 4
                Run Till Abort: 5
            Read mode:
                See self.read_modes
        """
        self.make_current()

        # Set the output flipper to direct light to this camera
        self.out("Setting flipper mirror:", end=" ")
        self.spec.ShamrockSetFlipperMirror(
            2,                              # it's an OUTPUT flipper
            cam_info[self.name]["port"])    # which port this camera is in

        # Set required parameters
        self.out("Setting acquisition mode:", end=" ")
        cam_lib.SetAcquisitionMode(self.acq_modes[acq_mode])
        self.out("Setting read mode:", end=" ")
        cam_lib.SetReadMode(self.read_modes[read_mode])

        # Set timing-related parameters
        self.out("Setting exposure time:", end=" ")
        cam_lib.SetExposureTime(float(exp_time))
        if accum_cycle_time is not None:
            self.out("Setting accumulation cycle time:", end=" ")
            cam_lib.SetAccumulationCycleTime(float(accum_cycle_time))
        if n_accums is not None:
            self.out("Setting number of accumulations:", end=" ")
            cam_lib.SetNumberAccumulations(n_accums)
        if kin_cycle_time is not None:
            self.out("Setting kinetic cycle time:", end=" ")
            cam_lib.SetKineticCycleTime(float(kin_cycle_time))
        if n_kinetics is not None:
            self.out("Setting number of kinetics:", end=" ")
            cam_lib.SetNumberKinetics(n_kinetics)
        self.out("Setting trigger mode:", end=" ")
        cam_lib.SetTriggerMode(self.trigger_modes[trigger])
        get_set_keep_cleans = (self.name == "Newton01" and read_mode == "fullbin"
            and trigger == "external")
        if keep_clean_mode == "wait":
            if get_set_keep_cleans:
                cam_lib.EnableKeepCleans(1)
            cam_lib.SetFastExtTrigger(0)
        elif keep_clean_mode== "trigger_abort":
            if get_set_keep_cleans:
                cam_lib.EnableKeepCleans(1)
            cam_lib.SetFastExtTrigger(1)
        elif keep_clean_mode=="disable":
            if get_set_keep_cleans:
                cam_lib.EnableKeepCleans(0)
            else:
                raise TypeError("Keep cleans can be disabled only on Newton, "
                    "in external trigger, full vertical binning mode")
        else:
            raise TypeError("keep_clean_mode value %r not recognized" %
                keep_clean_mode)

        # The camera isn't connected to the shutter, so tell it not to try
        # to do anything different
        self.out("Making camera ignore shutter:", end=" ")
        cam_lib.SetShutter(
            0,                  # Output TTL low open
            2,                  # Permanently closed: send no signals
            0., 0.              # Leave no extra opening/closing time
            )

        # Now that parameters are set, check actual timing
        actual_times = cam_lib.GetAcquisitionTimings(*(float,)*3)
        readout_time = cam_lib.GetReadOutTime(float)

        if get_set_keep_cleans:
            keep_clean_time = cam_lib.GetKeepCleanTime(float)
        else:
            keep_clean_time = -1.
        
        # Set up spectrometer
        if slit is not None:
            self.out("Setting slit width:", end=" ")
            self.spec.ShamrockSetSlit(float(slit))
        if wavelen is not None:
            self.spec.ShamrockSetWavelength(float(wavelen))
        
        # Exposure time, accum cycle time, kinetic cycle time, ____, ____
        return actual_times + (readout_time,) + (keep_clean_time,)

    def get_wavelen_array(self):
        self.make_current()
        self.spec.ShamrockSetNumberPixels(self.x)
        self.spec.ShamrockSetPixelWidth(self.x_width)
        wavelen_array = np.zeros((self.x,), dtype=np.float32)
        self.spec.ShamrockGetCalibration(wavelen_array.ctypes, self.x)
        return wavelen_array
    
    def get_new_array(self, n_images, read_mode="fullbin"):
        """Create an array to store the captured images"""
        return np.zeros((n_images,) + self.img_dims[read_mode], dtype=np.int32)

    def check_array(self, alloc, read_mode, n_images=None):
        # Check that supplied array works; raise an error if not
        if n_images is None:
            if len(alloc.shape) <= 1:
                n_images = 1
            else:
                n_images = len(alloc)
        correct_shape = (long(n_images),) + self.img_dims[read_mode]
        template = "Supplied array has wrong %s %r; should be %r"
        if alloc.shape != correct_shape:
            raise TypeError(template % ("shape", alloc.shape, correct_shape))
        # use != to compare dtypes, not `is not`
        if alloc.dtype != np.int32:
            raise TypeError(template % ("dtype", alloc.dtype, np.int32))

        return product(alloc.shape[1:])
    
    def expose(self, read_mode=None, get_data_dt=None, dark=False):
        "Start an acquisition. If `get_data_dt` is not None, wait & return data"
        if read_mode is None and get_data_dt is not None:
            raise TypeError("Need read_mode to get data")

        self.make_current()
        
        # Make sure camera and spectrometer are ready
        self.assert_idle()
        if dark:
            self.out("Making sure Shamrock shutter is closed...", end=" ")
            self.spec.ShamrockSetShutter(0)
        else:
            self.out("Opening Shamrock shutter...", end=" ")
            self.spec.ShamrockSetShutter(1)

        # Tell the camera to start
        self.out("Starting acquisition...", end=" ")
        try: cam_lib.StartAcquisition()
        except IOError as e:
            if not "DRV_ACQUIRING" in e.message:
                raise

        # If wait_time is given, wait for it to finish, get data, and return it
        # (Else return without doing anything more) 
        if get_data_dt is not None:
            time.sleep(get_data_dt)
            self.patient_assert_idle(dt=max(get_data_dt/100, 1), out=True)

            # If the shutter was opened, close it
            if not dark:
                self.out("Closing shutter...", end=" ")
                self.spec.ShamrockSetShutter(0)
            
            return self.get_data(read_mode)
    
    def get_data(self, read_mode, alloc=None, n_start=0):
        """Get data gathered by the camera

        Provide `alloc` to overwrite that array instead of making a new one. If
        there are more new images than spots for images in the array, store as
        many as possible.

        Parameters:
            read_mode: the read mode used by the camera to store these images
            alloc: a provided NumPy ndarray with the appropriate dimensions.
                Defaults to None, in which case a new array of the correct
                dimensions will be created.
            img_size: the dimensions of the 
            n_start: the index of alloc into which to copy the first copied
                image. Defaults to 0.

        Return value:
            if alloc:
                n = number of new images
            else:
                new NumPy ndarray containing data
        """
        self.make_current()

        # Check if camera is stabilized (or, for iDus01, unable to chedk the temp
        # because it's acquiring); if not, send warning
        temp, status = self.get_temp()
        if status not in ("DRV_TEMP_STABILIZED", "DRV_ACQUIRING"):
            self.out("Warning: %r; temp %d" % (status, temp))

        # Find out which images to gather, and how many total
        try:
            first, last = cam_lib.GetNumberNewImages(int, int)
        except IOError as e:
            #print(str(first) + str(last) + "\n")
            #print(e.message)
            if not "NO_NEW" in e.message:
                raise e
            else:
                if alloc is None:
                    return self.get_new_array(0, read_mode) # zero-length array
                else:
                    return 0 # zero new images

        # Check how many images are available
        n_avail = 1 + last - first
        # if n_avail == 0:
        #     print("nothing\n")
        # else:
        #     print("new images: " + str(n_avail) + "\n")
            
            
        # If none provided, make an array that can get all the images
        # Otherwise, see how many images will fit in the given array. Get a
        # slice from the array and update the index of the last image to
        # copy accordingly.
        if alloc is None:
            data = self.get_new_array(n_avail, read_mode)
            n_copied = n_avail
        else:
            n_copied = min(len(alloc) - n_start, n_avail)
            data = alloc[n_start : n_start+n_copied]
            last = first + n_copied - 1

        # Get number of elements in array, since function needs to know
        size = long(product(data.shape))

        # Copy data into array
        actual_first, actual_last = cam_lib.GetImages(first, last,
            data.ctypes, size, long, long)

        if first != actual_first or last != actual_last:
            msg = "Something weird happened and a different number of images"\
                  "were transferred than expected:\n" \
                  "\tfirst: %d" \
                  "\tactual_first: %d" \
                  "\tlast: %d" \
                  "\tactual_last%d" % (first, actual_first, last, actual_last)
            raise IOError(msg)
        
        # If the array was not user-supplied, return it.
        # Otherwise, return the number of images transferred to the array
        if alloc is None:
            return data
        # Otherwise, return the number of images transferred to the array
        else: 
            return n_copied
    
    def single_scan(self, read_mode="fullbin", dark=False, **kwargs):
        """Take a single exposure, wait for it to finish, then return the data

        All of `kwargs` is passed to self.prep_acquisition."""
        # Set up acquisition in single-scan mode.
        # Get actual exposure time --> send to self.expose to wait for data
        exp_time, _, _, readout_time, _ = self.prep_acquisition(
            acq_mode="single", read_mode=read_mode, **kwargs)
        actual_time = exp_time + readout_time
        #print("Exptime+readout: " + str(actual_time) + "\n")
        
        # Return data from single exposure
        return self.expose(read_mode, get_data_dt=actual_time, dark=dark)
    
    def accum(self, read_mode="fullbin", dark=False, **kwargs):
        "Take an accumulation of exposures, wait, then return the data"
        # Set defaults for kwarg passed to prep_acquisition
        kwargs.setdefault("accum_cycle_time", 0)
        kwargs.setdefault("n_accums", 1)

        # Set up acquisition in accumulation mode.
        # Get actual accumulation cycle time and number of cycles --> send to
        # self.expose to wait for data
        _, cycle_time, _, _, _ = self.prep_acquisition(acq_mode="accum",
            read_mode=read_mode, **kwargs)[1]
        n_accums = kwargs["n_accums"]
        
        # Return data from the accumulation
        tot_time = cycle_time*n_accums
        return self.expose(read_mode, get_data_dt=tot_time, dark=dark)

    def cont_get_data(self, read_mode, alloc, loop=False):
        """Keep track of where in the array to start copying data"""
        # Copy any new data, starting from current image
        n_copied = self.get_data(read_mode, alloc=alloc,
            n_start=self.n_saved)
        # Update which image we're on now (shouldn't exceed len(alloc))
        self.n_saved += n_copied
        # If we're done, stop the timer that's calling this and make sure the
        # camera is idle
        if self.n_saved >= len(alloc):
            if loop:
                self.n_saved %= len(alloc)
            else: # stop getting data
                self.timer.stop()
                self.patient_assert_idle(dt=1)

    def kinetic(self, alloc, read_mode="fullbin", dark=False, **kwargs):
        """Take a kinetic series and write the data continuously to alloc"""
        # Set defaults for kwargs passed to prep_aquisition
        kwargs.setdefault("accum_cycle_time", 0)
        kwargs.setdefault("n_accums", 1)
        kwargs.setdefault("kin_cycle_time", 0)
        kwargs.setdefault("n_kinetics", 1)
        n_accums = kwargs["n_accums"]
        n_kinetics = kwargs["n_kinetics"]

        # Set up acquisition in kinetic mode.
        # Get actual kinetic cycle time and number of cycles -->
        # determine how often to check for new data
        _, _, kin_time, _, _ = self.prep_acquisition(acq_mode="kinetic",
            read_mode=read_mode, **kwargs)

        # Check that alloc has the correct dimensions and dtype
        self.check_array(alloc, read_mode, img_size=n_kinetics)

        # Create a timer and hook it up to the alloc updater. Check for new
        # data ten times as frequently as we expect images (ms), but at least
        # 10 Hz
        interval = min(int(kin_time*100), 100)
        self.n_saved = 0
        self.timer = self.TimerClass(interval, self.cont_get_data,
            args=(read_mode, alloc))

        # Start the exposure, but don't wait to get data
        self.expose()
        self.timer.start()

    def scan_until_abort(self, alloc, read_mode="fullbin", dark=False,
        **kwargs):
        """Take images continuously until aborted, writing continuously"""
        # Set default for kwargs passed to prep_aquisition
        kwargs.setdefault("kin_cycle_time", 0)

        self.out("kin_cycle_time: %r" % kwargs["kin_cycle_time"])

        # Set up acquisition in kinetic mode.
        # Get actual kinetic cycle time and number of cycles -->
        # determine how often to check for new data
        _, _, kin_time, _, _ = self.prep_acquisition(
            acq_mode="scan_until_abort", read_mode=read_mode, **kwargs)
        # Memorize read mode so that memory can be emptied later
        self.scan_until_abort_read_mode = read_mode

        # Check that alloc has the correct dimensions and dtype & get img size
        img_size = self.check_array(alloc, read_mode)

        # Create a timer and hook it up to the alloc updater. Check for new
        # data ten times as frequently as we expect images (ms), but at least
        # 10 Hz
        interval = min(int(kin_time*100), 100)
        self.n_saved = 0
        self.timer = self.TimerClass(interval, self.cont_get_data,
            args=(read_mode, alloc), kwargs={"loop": True})

        # Start the acquisition and return
        self.expose()
        self.timer.start()
        return

    def abort(self):
        """Abort a scan_until_abort acquisition, unless it's already aborted"""
        try:
            self.assert_idle()
        except AssertionError:
            # camera is NOT idle
            # stop copying data from camera
            try:
                self.timer.stop()
            except AttributeError:
                pass
                # Make sure to get to AbortAcquisition, even if self.timer
                # doesn't exist due to some error.

            # stop camera from getting new data
            self.make_current()
            self.out("Aborting acquisition...", end=" ")
            cam_lib.AbortAcquisition()

            # clean out data register
            try:
                self.get_data(self.scan_until_abort_read_mode)
            except AttributeError:
                pass
                # Make sure to keep going in shut_down or whatever, even if
                # something here doesn't exist due to some error.

            try:
                # destroy the timer and slot so no new data copying is attempted
                del self.timer
            except AttributeError: pass

            try:
                # destroy variable used mid-acquisition to avoid confusion
                del self.n_saved
            except AttributeError: pass

    def cooler_off(self):
        self.make_current()
        self.out("Turning cooler off...", end=" ")
        cam_lib.CoolerOFF()

    def shut_down(self):
        """Shut down gracefully"""
        self.abort()
        self.cooler_off()
        self.out("Shutting down %r..." % self.name, end=" ")
        cam_lib.ShutDown()
        del self.handle

    def __del__(self):
        if self.is_initialized():
            self.shut_down()

class QAndorCamera(QAndorObject, AndorCamera):
    "Wrapped version of AndorCamera that implements PyQt signals and timing"
    TimerClass = WrappedQTimer

    initialization_done = QtCore.pyqtSignal()
    cooldown_started = QtCore.pyqtSignal(int)
    acquisition_timings = QtCore.pyqtSignal(float, float, float, float, float,
        str)
    new_images = QtCore.pyqtSignal(int)
    acquisition_done = QtCore.pyqtSignal(np.ndarray)
    abortion_done = QtCore.pyqtSignal()
    cooldown_stopped = QtCore.pyqtSignal()
    shutdown_done = QtCore.pyqtSignal()

    def __init__(self, serial, spec, out=None):
        QAndorObject.__init__(self)
        AndorCamera.__init__(self, serial, spec, out=out)

        cam_lib.message.connect(self.message)

    def __getattr__(self, name):
        AndorCamera.__getattr__(self, name)

    def initialize(self):
        AndorCamera.initialize(self)
        self.initialization_done.emit()

    def cooldown(self, temp=None):
        AndorCamera.cooldown(self, temp=temp)
        self.cooldown_started.emit(temp)

    def prep_acquisition_dict(self, kwargs):
        "allow signals to access prep_acquisition_dict"
        times = self.prep_acquisition(**kwargs)
        # keep track of whether internal or external trigger is desired
        args = times + (kwargs["trigger"],)
        self.acquisition_timings.emit(*args)

    def get_data(self, read_mode, alloc=None, n_start=0):
        if alloc is None:
            return AndorCamera.get_data(self, read_mode, alloc=alloc,
                                        n_start=n_start)
        else:
            n_copied = AndorCamera.get_data(self, read_mode, alloc=alloc,
                                            n_start=n_start)
            if n_copied > 0:
                self.new_images.emit(n_copied)
            return n_copied

    def single_scan(self, read_mode="fullbin", dark=False, **kwargs):
        data = AndorCamera.single_scan(self, read_mode=read_mode, dark=dark,
            **kwargs)
        self.acquisition_done.emit(data)

    def get_background(self, read_mode="fullbin", **kwargs):
        """Convenience function for signals to call single_scan(dark=True)"""
        self.single_scan(read_mode=read_mode, dark=True, **kwargs)

    def accum(self, read_mode="fullbin", dark=False, **kwargs):
        data = AndorCamera.accum(self, read_mode=read_mode, dark=dark, **kwargs)
        self.acquisition_done.emit(data)

    def cont_get_data(self, read_mode, alloc, loop=False):
        if alloc is None:
            data = AndorCamera.cont_get_data(self, read_mode, alloc=alloc,
                loop=loop)
            if self.n_saved >= len(alloc): # in which case loop=False
                self.acquisition_done.emit(data)
        else:
            AndorCamera.cont_get_data(self, read_mode, alloc=alloc,
                loop=loop)
            if self.n_saved >= len(alloc): # in which case loop=False
                self.acquisition_done.emit(alloc)

    def abort(self):
        AndorCamera.abort(self)
        self.abortion_done.emit()

    def cooler_off(self):
        AndorCamera.cooler_off(self)
        self.cooldown_stopped.emit()

    def shut_down(self):
        AndorCamera.shut_down(self)
        self.shutdown_done.emit()

    def __del__(self):
        AndorCamera.__del__(self)
        QAndorObject.__del__(self)

# Add known cameras to scope for importing
locals().update(
    {cameras[serial]: QAndorCamera(serial, Shamrock01) for serial in cameras}
    # {cameras[serial]: QAndorCamera(serial, spec) for serial in cameras}
    )