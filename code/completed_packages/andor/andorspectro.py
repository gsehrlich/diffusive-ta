"""Contains classes for integrating Andor spectrometer interfacing.

Spectrometers currently implemented: Andor Shamrock.
"""

from andordll import spec_lib
from _andorpath import _get_andor_path

class AndorShamrock(object):
    # Keep track of where and if this module is initialized
    _initialized_in = None

    def __init__(self, ind):
        """Integrates functionality for interacting with Andor Shamrock"""
        self.ind = ind

        if AndorShamrock._initialized_in is None:
            AndorShamrock.ShamrockInitialize()

        self.serial = self.ShamrockGetSerialNumber(str)
        self.name = name_dict[self.serial]

        self.attached_cameras = set()

    def __del__(self):
        """Shut down gracefully"""
        self.ShamrockClose()

    @classmethod
    def ShamrockInitialize(cla, IniPath=None):
        """Wrapper to update class variable _initialized_in with `IniPath`"""
        # Set default initialization location
        if IniPath is None:
            IniPath = _get_andor_path()

        spec_lib.ShamrockInitialize(IniPath)

        # Update the class variable
        cla._initialized_in = IniPath

    @classmethod
    def ShamrockClose(cla):
        """Wrapper to update class variable _initialized_in with `None`"""
        spec_lib.ShamrockClose()
        cla._initialized_in = None

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
        # accepts `device` as first argument; if so, wrap the function and make
        # it an instance attribute before giving it to the user
        if name not in ("ShamrockGetFunctionReturnDescription",
            "ShamrockGetNumberDevices"):
            new_func = self.wrap(func, name)
            self.__dict__[name] = new_func
            return new_func
        # Otherwise, leave it as is and make it a class attribute before giving
        # it to the user
        else:
            AndorShamrock.__dict__[name] = func
            return func

    def wrap(self, func, name):
        def new_func(*args):
            # Plug in the index as the first arg and pass the rest
            return func(self.ind, *args)
        new_func.func_name = name
        new_func.func_doc = "Wrapped function %r from %r" % (name, spec_lib)
        return new_func

# Given serial number, what variable name to use?
name_dict = {"SR2078": "spec"}

# Initialize all the spectrographs
AndorShamrock.ShamrockInitialize()

# Wrap all known attached spectrographs
specs = {}
for i in xrange(spec_lib.ShamrockGetNumberDevices(int)):
    try:
        spec = AndorShamrock(i)
    except KeyError: pass
    specs[spec.name] = spec
locals().update(specs)