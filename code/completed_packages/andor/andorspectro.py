"""Contains classes for integrating Andor spectrometer interfacing.

Spectrometers currently implemented: Andor Shamrock.
"""

from .andordll import spec_lib
from ._andorpath import _get_andor_path
from ._known import spectrometers
import types

class AndorShamrock(object):
    """Integrates functionality for interacting with Andor Shamrock"""

    def __init__(self, serial):
        self.serial = serial
        self.attached_cameras = set()
        self.initialized = False
        self.registered = False

    def initialize(self):
        """Initialize the Shamrock device wrapped by this object"""

        try:
            # Check if Shamrock library is initialized
            n = spec_lib.ShamrockGetNumberDevices(int)
        except IOError as e:
            if "NOT_INITIALIZED" in e.message:
                # If not, initialize it and try again
                spec_lib.ShamrockInitialize()
                n = spec_lib.ShamrockGetNumberDevices(int)
                self.initialized = True
            else:
                # This shouldn't happen; that function throws only one error
                raise

    def register(self):
        """Find the index of the spectrometer with this serial number"""
        # Find the index of the (first) spectro whose serial number matches
        for ind in xrange(spec_lib.ShamrockGetNumberDevices(int)):
            if spec_lib.ShamrockGetSerialNumber(ind, str) == self.serial:
                self.ind = ind
                break
        else:
            raise KeyError("Serial number %r not found" % self.serial)

        self.name = spectrometers[self.serial]

    def __getattr__(self, name):
        """Get the improved function from the wrapped library

        This function is only called if `name` is not already in the instance
        `__dict__` or the class tree. Once foreign functions are called once,
        their improved versions are added to the instance `__dict__`, so
        __getattr__ is not called again. ShamrockInitialize and ShamrockClose
        """
        # If the attribute is not found, let spec_lib raise the AttributeError
        func = getattr(spec_lib, name)

        # Check if it's one of the not-defined-as-amethod functions that
        # accepts `device` as first argument; if so, wrap it so that the first
        # index is already included and so that it handles errors intelligently
        if name not in ("ShamrockGetFunctionReturnDescription",
            "ShamrockGetNumberDevices"):
            new_func = self.wrap(func, name, include_ind=True)
        # Otherwise, don't bother with the first index, but still make it
        # handle errors intelligently
        else:
            new_func = self.wrap(func, name, include_ind=False)

        return new_func

    def wrap(self, func, name, include_ind):
        """Return a bound method that calls `func` intelligently"""
        if include_ind:
            # Plug in the index as the first arg and pass the rest to the
            # error handler
            new_func = lambda *args: self.handle_errors(func, (self.ind,)+args)
        else:
            # Just pass to the error handler
            new_func = lambda *args: self.handle_errors(func, args)

        # Write metadata for clarity
        new_func.func_name = name
        new_func.func_doc = "Wrapped function %r from %r" % (name, self)

        # Bind it to this object and provide its class
        return types.MethodType(new_func, self, self.__class__)

    @staticmethod
    def handle_errors(func, args):
            """Deal with errors if self is not intialized or not registered"""
            try:
                return func(*args)
            except IOError as e:
                # Iff self is not initialized, the spectrometer will say so
                if "NOT_INITIALIZED" in e:
                    raise IOError("Must initialize first: %r" % self)
                else:
                    raise
            except AttributeError as e:
                # Iff this object is not registered, it won't know its ind
                if "'ind'" in e.message:
                    raise IOError("Must register first: %r" % self)
                else:
                    raise

# Wrap all known attached spectrographs and add to this scope for importing
locals().update(
    {spectrometers[serial]: AndorShamrock(serial) for serial in spectrometers}
    )