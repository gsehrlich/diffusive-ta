"""Integrates functionality for interacting with Andor Cameras

WARNING: not suitable for rapid simultaneous interfacing with two or more
cameras. May not raise errors; may just yield garbage data.

Defines a class, `AndorCamera`, and two instances of it, `newton` and `idus`,
which bundle functionality from the andordll module for easy use from within
Python.

"""

import time
import numpy as np
from andordll import cam_lib
import andorspectro
from ctypes import c_int, byref
from PyQt4 import QtCore

def product(l):
    """Return the product of the elements in the iterable"""
    return reduce(lambda x, y: x*y, l)

class AndorCamera(QtCore.QObject):
    func_call = QtCore.pyqtSignal(str, tuple, dict)
    new_images = QtCore.pyqtSignal(int)
    done_acquiring = QtCore.pyqtSignal()

    # temp must be an int
    default_temp = {
        "newton": -70,
        "idus": -70
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
    trigger_type = 0 # TIL low open shutter
    flipper_ports = {
        "newton": 0,
        "idus": 1,
        }

    # Makes it possible to call arbitrary methods through signals
    @QtCore.pyqtSlot(str, tuple, dict)
    def _call(self, name, args, kwargs):
        getattr(self, str(name))(*args, **kwargs)
    
    def make_current(self, out=True):
        """Make sure cam_lib knows this is the current camera"""
        if cam_lib.GetCurrentCamera(int) != self.handle:
            if out: print "Making %s current:" % self.name,
            cam_lib.SetCurrentCamera(self.handle)
    
    # defines `self.temp` as a property with the default getter
    @property
    def temp(self):
        return self._temp
    
    # Now that `self.temp` is a property, create a non-default setter
    @temp.setter
    def temp(self, temp):
        """Change temp to update the camera's goal temperature"""
        if temp is None:
            self._temp = self.default_temp[self.name]
        else:
            self._temp = int(temp)
        print "Setting %s temperature:" % self.name,
        cam_lib.SetTemperature(self._temp)
            
    def __init__(self, handle, spec, temp=None):
        """Class for easy use of Andor cameras"""
        # Initialize this as a QtCore.QObject so that it can have bound signals
        super(AndorCamera, self).__init__()

        # Tell the camera and spectrometer they've been attached
        self.spec = spec
        self.spec.attached_cameras.add(self)
        
        # Store the way to handle used to access this camera, then make sure
        # the rest of the calls to cam_lib refer to this camera
        self.handle = handle
        self.make_current(out=False) # no name yet; would throw AttributeError
        
        print "Initializing..."
        cam_lib.Initialize()
        
        # Use the camera serial number to figure out which one it is
        self.serial_no = cam_lib.GetCameraSerialNumber(int)
        self.name = name_dict[self.serial_no]
        print "Initialized %s." % self.name
        
        # Set up detector size information
        x, y = cam_lib.GetDetector(int, int)
        self.x = long(x)
        self.y = long(y)
        self.img_dims = {
            "image": (self.y, self.x),
            "fullbin": (self.x,)
            }

        self.hardware_version = cam_lib.GetHardwareVersion(*(int,)*6)
        try:
            self.n_VS_speeds = cam_lib.GetNumberVSSpeeds(int)
        except IOError as e:
            self.n_VS_speeds = 0
            print "GetNumberVSSpeeds: %s" % e.message
        if self.n_VS_speeds > 0:
            self.VS_speeds = tuple(cam_lib.GetVSSpeed(i, int)
                                    for i in xrange(self.n_VS_speeds))
        
        # TODO, maybe: figure out first two params that work
        #self.n_HS_speeds = cam_lib.GetNumberHSSpeeds(1, 0, int)
        #self.HS_speeds = tuple((cam_lib.GetHSSpeed(i, 1, 0, float)
        #                        for i in xrange(self.n_HS_speeds)))
        
        self.mintemp, self.maxtemp = cam_lib.GetTemperatureRange(int, int)

        # Set the goal temp and start cooling down
        self.temp = temp
        print "Turning %s cooler on:" % self.name,
        cam_lib.CoolerON()

        self.func_call.connect(self._call)

    def __del__(self):
        """Shut down gracefully"""
        self.make_current()
        cam_lib.CoolerOFF()
        cam_lib.ShutDown()
        
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
            self.flipper_ports[self.name])   # which port this camera is in

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
            cam_lib.SetFastExtTrigger(fast_external)

        # The camera isn't connected to the shutter, so tell it not to try
        # to do anything different
        print "Making camera ignore shutter:",
        cam_lib.SetShutter(
            self.trigger_type,  # Whether output TTL low open or TTL high open
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
    
    def get_data(self, read_mode, alloc=None):
        """Return data gathered by the camera

        Provide `alloc` to overwrite that array instead of making a new one
        """
        self.make_current()
        
        # Find out which images to gather, and how many total
        first, last = cam_lib.GetNumberNewImages(long, long)
        n_images = 1 + last - first

        # Make a new array, if necessary
        if alloc is None:
            data = self.get_new_array(n_images, read_mode)
        else:
            data = alloc

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
        
        # If the array was not user-supplied, return it (else do nothing more)
        if alloc is None:
            return data
    
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

    def _copy_imgs(self, alloc, img_size, n_start=0):
        """Copy new images from cam into specified memory; return number new"""
        try:
            first, last = cam_lib.GetNumberNewImages(int, int)
        except IOError as e:
            if not "NO_NEW" in e.message:
                raise e
            else:
                return 0 # number of new images = 0
        else:
            n_new = 1 + last - first
            n_copied = min(len(alloc) - n_start, n_new)
            actual_last = last - (n_new - n_copied)

            # Get as much new data as will fit
            cam_lib.GetImages(first, actual_last,
                alloc[n_start : min(len(alloc), n_start+n_copied)].ctypes,
                n_copied*img_size, long, long)

            # Alert whatever called this function that new images are available
            self.new_images.emit(n_new)

            return n_new

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

        # Check that alloc has the correct dimensions and dtype & get img size
        img_size = self.check_array(alloc, n_kinetics, read_mode)

        # Start the exposure, but don't wait to get data
        self.expose()

        # LOOP: continuously save data to the array until every accumulation
        # is copied.
        n_saved = 0
        while n_saved < n_kinetics:
            n_new = self._copy_imgs(alloc, img_size, n_start=n_saved)

            # Update counters and wait for the next loop
            n_saved += n_new
            time.sleep(kin_time*0.1)

        self.patient_assert_idle(dt=1)
        self.done_acquiring.emit()

    def scan_until_abort(self, alloc, read_mode="fullbin", dark=False, **kwargs):
        """Take images continuously until aborted, writing continuously"""
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

        # Memorize read mode so that memory can be emptied later
        self.scan_until_abort_read_mode = read_mode

        # Check that alloc has the correct dimensions and dtype & get img size
        img_size = self.check_array(alloc, 1, read_mode)

        # Create a QTimer and hook it up to the alloc updater. Then create
        # another signal, for stop acquisition, and hook it up to timer.stop
        # and the acquisition updater
        def _tmp():
            self._copy_imgs(alloc, img_size)
            self.new_images.emit(1)
        self.scan_until_abort_slot = _tmp
        self.scan_until_abort_timer = QtCore.QTimer()
        self.scan_until_abort_timer.setInterval(int(kin_time)*100) # ms!
        self.scan_until_abort_timer.timeout.connect(self.scan_until_abort_slot)

        # Start the acquisition and return
        self.expose()
        self.scan_until_abort_timer.start()
        return

    def abort(self):
        """Abort a scan_until_abort acquisition"""
        # stop copying data from camera
        self.scan_until_abort_timer.stop()

        # stop camera from getting new data
        self.make_current()
        cam_lib.AbortAquisition()

        # clean out data register
        self.get_data(self.scan_until_abort_read_mode)

        # destroy the timer and slot so no new data copying is attempted
        del self.scan_until_abort_timer, self.scan_until_abort_slot

# Doesn't work yet
"""
    def cont_single_scans(self, **kwargs):
        self.make_current()
        
        read_mode = kwargs.pop("read_mode", "image")
        kwargs.setdefault("kin_cycle_time", 0)
        actual_times = self.prep_acquisition(acq_mode=1, read_mode=read_mode, **kwargs)
        
        #w = pg.image()
        data = self.get_new_array(n_images=1, read_mode=read_mode)
        while w.isVisible():
            cam_lib.StartAcquisition()
            time.sleep(1)
            self.get_data(read_mode=read_mode, data=data)
            w.setImage(data)
"""

name_dict = {
    17910: "newton",
    17911: "idus"
    }

cams = {}
for i in xrange(cam_lib.GetAvailableCameras(int)):
    cam = AndorCamera(cam_lib.GetCameraHandle(i, int), andorspectro.spec)
    cams[cam.name] = cam
locals().update(cams)