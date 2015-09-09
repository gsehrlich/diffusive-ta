"""Integrates functionality for interacting with Andor Cameras

WARNING: not thread-safe with two simultaneous cameras. May not raise errors;
may just yield garbage data.

Defines a class, `AndorCamera`, and two instances of it, `newton` and `idus`,
which bundle functionality from the andordll module for easy use from within
Python.

"""

import time
import numpy as np
from .andordll import cam_lib
from .andorspectro import spec
from ._known import cameras, cam_info
from ctypes import c_int, byref
from PyQt4 import QtCore
from contextlib import contextmanager

def product(l):
    """Return the product of the elements in the iterable"""
    return reduce(lambda x, y: x*y, l)

class CameraHandle(object):
    def __init__(self, keep_open):
        self.keep_open = keep_open

class AndorCamera(QtCore.QObject):
    "Control Andor cameras attached to a USB-controlled Andor Shamrock"
    func_call = QtCore.pyqtSignal(str, tuple, dict)
    new_images = QtCore.pyqtSignal(int)
    done_acquiring = QtCore.pyqtSignal()
    abort_acquisition = QtCore.pyqtSignal()
    aborted = QtCore.pyqtSignal()
    already_idle = QtCore.pyqtSignal()

    # temp must be an int
    default_temp = {
        "newton": -70,
        "idus": -70
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

    @staticmethod
    def _is_initialized(handle):
        "Return True if the handle is already initialized, else False"
        # Set handle as current
        print "Setting camera with handle %r as current:" % handle,
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

    @classmethod
    def get_handle_dict(cls, keep_serials_open=()):
        """Return a dict of serial numbers: handles.

        Warning: all cameras that were not already initialized will be
        initialized and then shut down (unless told to keep them open)."""
        # If this has already been done, just return the dict
        if hasattr(cls, "handle_dict"):
            return cls.handle_dict

        # Initialize the empty dict and begin looping through all the cameras
        print "Finding camera handles of all serial numbers..."
        handle_dict = {}
        for i in xrange(cam_lib.GetAvailableCameras(int)):
            # Get the handle
            handle = cam_lib.GetCameraHandle(i, int)

            # Set handle to current and find out whether it's initialized yet
            was_preinitialized = cls._is_initialized(handle)

            # If not, initialize it
            if not was_preinitialized:
                print "Initializing:",
                cam_lib.Initialize()

            # Find and store the serial number
            serial = cam_lib.GetCameraSerialNumber(int)
            handle_dict[serial] = handle
            print "Found handle %r for serial %r" % (handle, serial)

            # If the camera wasn't already inited, and the function wasn't
            # instructed to keep it open, close it.
            if not was_preinitialized and serial not in keep_serials_open:
                print "Shutting down serial %r" % serial
                cam_lib.ShutDown()

        # Store this in the class and then return it
        cls.handle_dict = handle_dict
        return handle_dict

    # Makes it possible to call arbitrary methods through signals
    @QtCore.pyqtSlot(str, tuple, dict)
    def _call(self, name, args, kwargs):
        getattr(self, str(name))(*args, **kwargs)
    
    def make_current(self, out=True):
        """Make sure cam_lib knows this is the current camera

        If handle is not defined yet, self.__getattr__ will raise a good error.
        """
        if cam_lib.GetCurrentCamera(int) != self.handle:
            if out: print "Making %s current:" % self.name,
            cam_lib.SetCurrentCamera(self.handle)
            
    def __init__(self, serial, spec):
        """Set up attributes for AndorCamera instance"""
        # Initialize this as a QtCore.QObject so that it can have bound signals
        super(AndorCamera, self).__init__()

        # Connect signals to their slots
        self.func_call.connect(self._call)
        self.abort_acquisition.connect(self.abort)

        # Store the serial number of the desired camera, and get the name
        self.serial = serial
        self.name = cameras[self.serial]

        # Tell the camera and spectrometer they've been attached
        self.spec = spec
        self.spec.attached_cameras.add(self)

    def initialize(self, cooldown=True, temp=None):
        """Initialize the Andor DLL wrapped by this object"""
        # Try handle corresponding to index given in cam_info
        ind = cam_info[self.name]["index"]
        handle = cam_lib.GetCameraHandle(ind, int)

        # Set handle as current and find out whether it's initialized yet
        was_preinitialized = self._is_initialized(handle)
        if not was_preinitialized:
            # If not, initialize it
            print "Initializing:",
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
            print ("Wrong serial number %r. Should be %r." % 
                (serial, self.serial)),
            handle_dict = self.get_handle_dict(keep_serials_open=(self.serial,))
            self.handle = handle_dict[self.serial]

            # Then shut down the one that's wrong.
            if not was_preinitialized:
                print ("Setting wrong camera with handle %r as current:" % 
                        handle),
                cam_lib.SetCurrentCamera(handle)
                print "Shutting down wrong camera:",
                cam_lib.ShutDown()

    def register(self):
        """Fetch information about this camera from DLL"""
        self.make_current()

        # Set up detector size information
        x, y = cam_lib.GetDetector(int, int)
        self.x = long(x)
        self.y = long(y)
        self.img_dims = {
            "image": (self.y, self.x),
            "fullbin": (self.x,)
            }

    def __getattr__(self, name):
        """Throw comprehensible error if camera is not yet registered.

        This function will only be called if the attribute is not found through
        the usual means (e.g. the object __dict__ and all class and superclass
        __dict__s)."""
        # Create standard message
        message = "%r object has no attribute %r" % (type(self), name)
        # If it's one of the attribute names defined in initialize or register,
        # add additional explanation.
        if name == "handle":
            message += ". Must call .initialize() first"
        elif name in ("x", "y", "img_dims"):
            message += ". Must call .register() first"

        raise AttributeError(message)

    def cooldown(self, temp=None):
        """Start the camera cooldown"""
        self.make_current()
        # Fetch the target temperature and then set it
        if temp is None:
            temp = int(cam_info[self.name]["temp"])
        else:
            temp = int(temp)
        print "Setting temp to %d:" % temp,
        cam_lib.SetTemperature(temp)

        # Start the cooldown
        # If no temperatue provided, will use whatever default the lib/cam has
        print "Turning cooler on:",
        cam_lib.CoolerON()

    def __del__(self):
        self.shut_down()
        
    def get_temp(self, out=False):
        """Return the camera's current temp (not goal temp)"""
        self.make_current()
        temp = c_int()
        # don't want usual return behavior, so go to ctypes.cdll object
        ret = cam_lib.lib.GetTemperature(byref(temp))
        if out:
            print "\r\t%d, %s" % (temp.value, cam_lib.errs[ret])
        return temp.value, ret
        
    def wait_until_cool(self, out=False, dt=5):
        """Do nothing until the camera is stabilized at the goal temp"""
        self.make_current()

        stabilized = False
        if out:
            print "Waiting for temp to reach %d" % self.temp
            print "Temp is: "
        while not stabilized:
            temp, ret = self.get_temp(out=out)
            if ret == cam_lib.consts["DRV_TEMPERATURE_STABILIZED"]:
                stabilized = True
            # Wait dt seconds in between checking whether it's stabilized
            if not stabilized: time.sleep(dt)
                
    def assert_idle(self):
        """Make sure the camera is idle; if not, raise AssertionError"""
        self.make_current()
        assert cam_lib.GetStatus(int) == cam_lib.consts["DRV_IDLE"]

    def patient_assert_idle(self, dt=1, out=False):
        """Give the camera a little extra time to become idle if necessary"""
        try:
            self.assert_idle()
        except AssertionError:
            if out:
                print "Waiting an extra %g seconds for idle..." % dt
            time.sleep(dt)
            self.assert_idle()        
        
    def prep_acquisition(self, acq_mode, read_mode, exp_time=0,
                         accum_cycle_time=None, n_accums=None,
                         kin_cycle_time=None, n_kinetics=None,
                         trigger="internal", fast_external=False,
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
        print "Setting flipper mirror:"
        self.spec.ShamrockSetFlipperMirror(
            2,                              # it's an OUTPUT flipper
            cam_info[self.name]["port"])    # which port this camera is in

        # Set required parameters
        print "Setting acquisition mode:",
        cam_lib.SetAcquisitionMode(acq_mode)
        print "Setting read mode:",
        cam_lib.SetReadMode(self.read_modes[read_mode])

        # Set timing-related parameters
        print "Setting exposure time:",
        cam_lib.SetExposureTime(float(exp_time))
        if accum_cycle_time is not None:
            print "Setting accumulation cycle time:",
            cam_lib.SetAccumulationCycleTime(float(accum_cycle_time))
        if n_accums is not None:
            print "Setting number of accumulations:",
            cam_lib.SetNumberAccumulations(n_accums)
        if kin_cycle_time is not None:
            print "Setting kinetic cycle time:",
            cam_lib.SetKineticCycleTime(float(kin_cycle_time))
        if n_kinetics is not None:
            print "Setting number of kinetics:",
            cam_lib.SetNumberKinetics(n_kinetics)
        print "Setting trigger mode:",
        cam_lib.SetTriggerMode(self.trigger_modes[trigger])
        if fast_external:
            cam_lib.SetFastExtTrigger(1)

        # The camera isn't connected to the shutter, so tell it not to try
        # to do anything different
        print "Making camera ignore shutter:",
        cam_lib.SetShutter(
            0,                  # Output TTL low open
            2,                  # Permanently closed: send no signals
            0., 0.              # Leave no extra opening/closing time
            )

        # Now that parameters are set, check actual timing
        actual_times = cam_lib.GetAcquisitionTimings(*(float,)*3)
        
        # Set up spectrometer
        if slit is not None:
            print "Setting slit width:",
            self.spec.ShamrockSetSlit(float(slit))
        if wavelen is not None:
            self.spec.ShamrockSetWavelength(float(wavelen))
        
        return actual_times
    
    def get_new_array(self, n_images, read_mode):
        """Create an array to store the captured images"""
        return np.zeros((n_images,) + self.img_dims[read_mode], dtype=np.int32)

    def check_array(self, alloc, n_images, read_mode):
        # Check that supplied array works; raise an error if not
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
            print "Making sure Shamrock shutter is closed..."
            self.spec.ShamrockSetShutter(0)
        else:
            print "Opening Shamrock shutter..."
            self.spec.ShamrockSetShutter(1)

        # Tell the camera to start
        print "Starting acquisition..."
        cam_lib.StartAcquisition()

        # If wait_time is given, wait for it to finish, get data, and return it
        # (Else return without doing anything more) 
        if get_data_dt is not None:
            time.sleep(get_data_dt)
            self.patient_assert_idle(dt=max(get_data_dt/100, 1), out=True)

            # If the shutter was opened, close it
            if not dark:
                print "Closing shutter..."
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

        # Check if camera is stabilized; if not, send warning
        temp, ret = self.get_temp()
        if ret != cam_lib.consts["DRV_TEMPERATURE_STABILIZED"]:
            print "Warning: %r; temp %d" % (cam_lib.errs[ret], temp)

        # Find out which images to gather, and how many total
        try:
            first, last = cam_lib.GetNumberNewImages(int, int)
        except IOError as e:
            if not "NO_NEW" in e.message:
                raise e
            else:
                return 0 # zero new images

        # Check how many images are available
        n_avail = 1 + last - first

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
        # Otherwise, send the signal that new images are available, and
        # return the number of images transferred to the array
        else: 
            self.new_images.emit(n_copied)
            return n_copied
    
    def single_scan(self, read_mode="fullbin", dark=False, **kwargs):
        """Take a single exposure, wait for it to finish, then return the data

        All of `kwargs` is passed to self.prep_acquisition."""
        # Set up acquisition in single-scan mode.
        # Get actual exposure time --> send to self.expose to wait for data
        actual_time, _, _ = self.prep_acquisition(acq_mode=1,
            read_mode=read_mode, **kwargs)
        
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
        _, cycle_time, _ = self.prep_acquisition(acq_mode=2,
            read_mode=read_mode, **kwargs)[1]
        n_accums = kwargs["n_accums"]
        
        # Return data from the accumulation
        tot_time = cycle_time*n_accums
        return self.expose(read_mode, get_data_dt=tot_time, dark=dark)

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
        _, _, kin_time = self.prep_acquisition(acq_mode=3,
            read_mode=read_mode, **kwargs)

        # Check that alloc has the correct dimensions and dtype
        self.check_array(alloc, n_kinetics, read_mode)

        # Start the exposure, but don't wait to get data
        self.expose()

        # LOOP: continuously save data to the array until every accumulation
        # is copied.
        n_saved = 0
        while n_saved < n_kinetics:
            n_new = self.get_data(read_mode, alloc=alloc, n_start=n_saved)

            # Update counters and wait for the next loop
            n_saved += n_new
            time.sleep(kin_time*0.1)

        self.patient_assert_idle(dt=1)
        self.done_acquiring.emit()

    def scan_until_abort(self, alloc, read_mode="fullbin", dark=False, **kwargs):
        """Take images continuously until aborted, writing continuously"""
        # Set default for kwargs passed to prep_aquisition
        kwargs.setdefault("kin_cycle_time", 0)

        print "kin_cycle_time: %r" % kwargs["kin_cycle_time"]

        # Set up acquisition in kinetic mode.
        # Get actual kinetic cycle time and number of cycles -->
        # determine how often to check for new data
        _, _, kin_time = self.prep_acquisition(acq_mode=5,
            read_mode=read_mode, **kwargs)
        # Memorize read mode so that memory can be emptied later
        self.scan_until_abort_read_mode = read_mode

        # Check that alloc has the correct dimensions and dtype & get img size
        img_size = self.check_array(alloc, 1, read_mode)

        # Create a QTimer and hook it up to the alloc updater. Then create
        # another signal, for stop acquisition, and hook it up to timer.stop
        # and the acquisition updater
        def _tmp():
            n = self.get_data(read_mode, alloc=alloc)
            if n > 0:
                self.new_images.emit(n)
        self.scan_until_abort_slot = _tmp
        self.scan_until_abort_timer = QtCore.QTimer()
        # check ten times as frequently as we expect images (ms), but at least
        # 10 Hz
        self.scan_until_abort_timer.setInterval(min(int(kin_time*100), 100))
        self.scan_until_abort_timer.timeout.connect(self.scan_until_abort_slot)

        # Start the acquisition and return
        self.expose()
        self.scan_until_abort_timer.start()
        return

    def abort(self):
        """Abort a scan_until_abort acquisition, unless it's already aborted"""
        try:
            self.assert_idle()
        except AssertionError:
            # camera is NOT idle
            # stop copying data from camera
            self.scan_until_abort_timer.stop()

            # stop camera from getting new data
            self.make_current()
            cam_lib.AbortAcquisition()

            # clean out data register
            self.get_data(self.scan_until_abort_read_mode)

            # destroy the timer and slot so no new data copying is attempted
            del self.scan_until_abort_timer, self.scan_until_abort_slot

            self.aborted.emit()
        else:
            self.already_idle.emit()

    def shut_down(self):
        """Shut down gracefully"""
        self.make_current()
        cam_lib.CoolerOFF()
        cam_lib.ShutDown()

# Add known cameras to scope for importing
locals().update(
    {cameras[serial]: AndorCamera(serial, spec) for serial in cameras}
    )