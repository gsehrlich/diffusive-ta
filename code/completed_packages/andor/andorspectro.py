"""Contains classes for integrating Andor spectrometer interfacing.

Spectrometers currently implemented: Andor Shamrock.
"""

from __future__ import print_function
from .andordll import spec_lib
from ._andorpath import _get_andor_path
from ._known import spectrometers
from ._q_andor_object import QAndorObject
import types
from PyQt4 import QtCore

class AndorShamrock(object):
    """Integrates functionality for interacting with Andor Shamrock"""

    @property
    def out(self):
        """Define `out` as a new property with the standard getter"""
        return self._out
    @out.setter
    def out(self, val):
        """Whenever `out` is changed, update spec_lib too"""
        spec_lib.out = val
        self._out = val

    def __init__(self, serial, out=print):
        self.serial = serial
        self.attached_cameras = set()

        # Store the passed out function (implicitly updating spec_lib)
        self.out = out

    @staticmethod
    def is_initialized():
        """Check if the Shamrock library is initialized."""
        try:
            # Check if Shamrock library is already initialized
            spec_lib.ShamrockGetNumberDevices(int)
            return True
        except IOError as e:
            if "NOT_INITIALIZED" in e.message:
                # If not, return False
                return False
            else:
                # This shouldn't happen; that function throws only one error
                raise

    def initialize(self):
        """Initialize the Shamrock DLL wrapped by this object"""
        if not self.is_initialized():
            self.out("Initializing Shamrock library:", end=" ")
            spec_lib.ShamrockInitialize()

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

    def shut_down(self):
        """Shut down gracefully"""
        self.out("Shutting down Shamrock library...", end=" ")
        self.ShamrockClose()

    def __getattr__(self, name):
        """Get the improved function from the wrapped library

        This function is only called if `name` is not already in the instance
        `__dict__` or the class tree. Once foreign functions are called once,
        their improved versions are added to the instance `__dict__`, so
        __getattr__ is not called again.
        """
        # If the attribute is named 'ind', it's because this spectrometer has
        # not yet been registered
        if name == "ind":
            raise IOError("Spectrometer index not found. "
                          "Must register first: %r" % self)

        # Otherwise let spec_lib raise the AttributeError
        func = getattr(spec_lib, name)

        # Check if it's one of the not-defined-as-a-method functions that
        # accepts `device` as first argument; if so, wrap it so that the first
        # index is already included and so that it handles errors intelligently
        if name not in ("ShamrockGetFunctionReturnDescription",
            "ShamrockGetNumberDevices", "ShamrockClose", "ShamrockInitialize"):
            new_func = self._wrap(func, name)
        # Otherwise, don't bother with the first index and make it a static
        # method, but still make it handle errors intelligently
        else:
            new_func = self._wrap(func, name, static=True)

        return new_func

    def _wrap(self, func, name, static=False):
        """Return a bound method that calls `func` intelligently"""
        if static:
            # Pass to the error handler without changes
            new_func = lambda *args: self._handle_notinit(func, args)

            # Write metadata for clarity
            self._write_metadata(new_func, name)

            # Build and store a static method built from that function
            new_func = staticmethod(new_func)
            setattr(AndorShamrock, name, new_func)

            # Need to introspect to get a callable version
            return getattr(self, name)
        else:
            # Plug in the index as the first arg and pass the rest to the
            # error handler. This will be a method, so make the first arg
            # the instance. Use `slf` to avoid referencing self.
            new_func = (
                lambda slf, *args: slf._handle_notinit(func, (slf.ind,)+args)
                )

            # Write metadata for clarity
            self._write_metadata(new_func, name)

            # Bind it to this instance as a method
            return types.MethodType(new_func, self, self.__class__)

    def _write_metadata(self, func, name):
        """Give func a new name and docstring"""
        func.func_name = name
        func.func_doc = "Wrapped function %r from %r" % (name, self)

    @staticmethod
    def _handle_notinit(func, args):
            """Deal with error if self is not intialized"""
            try:
                return func(*args)
            except IOError as e:
                # Iff self is not initialized, the spectrometer will say so
                if "NOT_INITIALIZED" in e:
                    raise IOError("Must initialize first: %r" % self)
                else:
                    raise

    def __del__(self):
        self.shut_down()

class QAndorShamrock(QAndorObject, AndorShamrock):
    """Wrapped version of QAndorShamrock that implements four PyQt signals"""
    initialization_done = QtCore.pyqtSignal()
    registration_done = QtCore.pyqtSignal()
    shutdown_done = QtCore.pyqtSignal()
    def __init__(self, serial, out=None):
        QAndorObject.__init__(self)
        AndorShamrock.__init__(self, serial, out=out)

        spec_lib.message.connect(self.message)

    def initialize(self):
        AndorShamrock.initialize(self)
        self.initialization_done.emit()

    def register(self):
        AndorShamrock.register(self)
        self.registration_done.emit()

    def shut_down(self):
        AndorShamrock.shut_down(self)
        self.shutdown_done.emit()\

    def __getattr__(self, name):
        return AndorShamrock.__getattr__(self, name)

    def __del__(self):
        AndorShamrock.__del__(self)
        QAndorObject.__del__(self)

# Wrap all known attached spectrographs and add to this scope for importing
locals().update(
    {spectrometers[serial]: QAndorShamrock(serial) for serial in spectrometers}
    )