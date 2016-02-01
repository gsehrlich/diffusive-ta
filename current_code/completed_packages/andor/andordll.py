"""
Wraps ctypes libraries for Andor SDK for cameras and Shamrock spectrometer

Defines a class, AndorDLL, and two instances of it, cam_lib and spec_lib.
These instances wrap ctypes libraries so that the DLL functions are accessible
as attributes of the instances and are faster and more intuitive to use.

Given a Shamrock SDK function definition

    unsigned int WINAPI ShamrockGetSerialNumber(int device, char *serial)

    Description     Returns the device serial number.

    Parameters      int device: Shamrock to interrogate
                    char *serial: pointer to the device serial number

    Return          SHAMROCK_SUCCESS                serial number returned
                    SHAMROCK_NOT_INITIALIZED        Shamrock not initialized
                    SHAMROCK_P1INVALID              Invalid device
                    SHAMROCK_COMMUNICATION_ERROR    Unable to communicate w...

the c_types version would be called as follows:

    >>> import ctypes
    >>> lib = ctypes.cdll.LoadLibrary("ShamrockCIF.dll")
    >>> serial = ctypes.c_char_p("")
    >>> ret = lib.ShamrockGetSerialNumber(0, serial)
    >>> ret   # Look in ShamrockCIF.h to find SHAMROCK_NOT_INITIALIZED
    20275

    ... # Initialize

    >>> ret = lib.ShamrockGetSerialNumber(0, serial)
    >>> ret  # its value is SHAMROCK_SUCCESS
    20202
    >>> serial.value  
    'SR####'

This is a lot of work for something that shouldn't be that hard. The wrapped
version is used instead as follows:

    >>> from andor.andordll import spec_lib
    >>> serial = spec_lib.ShamrockGetSerialNumber(0, str)  # str: builtin type
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/path/to/package/andor/andordll.py", line 199, in new_func
        raise IOError(msg)
    IOError: SHAMROCK_NOT_INITIALIZED # Raise recognizable error

    ... # Initialize

    >>> serial = spec_lib.ShamrockGetSerialNumber(0, str)
    >>> serial
    'SR####'

The original function is available under the `lib` attribute:

    >>> spec_lib.lib.ShamrockGetSerialNumber
    <_FuncPtr object at 0x################>

Three things are different about the wrapped function:
  * Instead of pointers to the value(s) of interest, accept their Python
    equivalent data types;
  * Instead of storing the desired value(s) in said pointers, return it/them:
    a single value if there is only one pointer, or a tuple if there are at
    least two (and if there are none, instead print the SUCCESS code whose
    number would normally be returned);
  * Instead of returning the error/success code: if it has 'SUCCESS' in it,
    do nothing, and otherwise throw an IOError with the code as the message.
So all you need to do is change the arguments you pass, as follows:
  * ctypes.byref(c_int()) --> int  (as in the Python type, NOT a string)
  * ctypes.byref(c_long()) --> long
  * ctypes.byref(c_float()) --> float
  * ctypes.c_char_p("") --> str
N.B.: THIS CLASS CANNOT CURRENTLY AUTO-CREATE ARRAYS TO RETURN. So:
  * numpy.zeros((n, n)).ctypes --> call the function manually from .lib

Examples:

    >>> spec_lib.ShamrockInitialize('.')
    SHAMROCK_SUCCESS

    >>> spec_lib.ShamrockGetGrating(0, int)
    1

    >>> spec_lib.ShamrockGetWavelengthLimits(0, 1, float, float)
    (0.0, 11249.0)

    >>> cam_lib.Initialize('.')

    >>> import time
    >>> cam_lib.CoolerON()
    DRV_SUCCESS
    >>> stabilized = False
    >>> while not stabilized:
    ...     try:
    ...         cam_lib.GetTemperature(int)
    ...     except IOError as e:
    ...         if not "TEMP_STABILIZED" in e.message:
    ...             print "Not yet stabilized. Waiting 1000 seconds..."
    ...         else:
    ...             stabilized = True
    ...             print "Stabilized!"
    Not yet stabilized. Waiting 1000 seconds...
    Not yet stabilized. Waiting 1000 seconds...
    Stabilized!
    >>> temp = ctypes.c_int()
    >>> cam_lib.lib.GetTemperature(ctypes.byref(temp)) # Returns DRV_SUCCESS
    20002
    >>> temp.value
    -85

    >>> import numpy as np
    >>> data = np.zeros((256, 1024), dtype=int32)
    >>> size = long(256*1024)
    >>> first, last = cam_lib.GetNumberNewImages(long, long)
    >>> validfirst, validlast = ctypes.c_long(), ctypes.c_long()
    >>> ret = cam_lib.lib.GetImages(first, last, data.ctypes, size,
    ...                             validfirst, validlast)

For documentation on individual functions, please see the relevant Andor SDK
documentation.

"""

from __future__ import print_function
from ctypes import *
import re
import os
import platform
from ._andorpath import _andor_exec
from ._known import dlls_32, dlls_64
from ._q_andor_object import QAndorObject

class AndorDLL(object):
    # Constructors for pointers that are used to get return values
    ptr_constrs = {
        int: lambda: byref(c_int()),
        long: lambda: byref(c_long()),
        float: lambda: byref(c_float()),
        str: lambda: create_string_buffer(64)
        }
    # Constructors for ctypes variables that will ensure Python variables
    # are passed to ctypes as the correct type
    var_constrs = {
        int: c_int,
        float: c_float
        }
    
    def new_ptr(self, typ):
        """Return a new pointer of the specified type"""
        return self.ptr_constrs[typ]()
    
    def new_var(self, arg):
        """Return a new variable with the same value and equivalent ctype"""
        return self.var_constrs[type(arg)](arg)
    
    def convert_arg(self, arg):
        """Return the argument converted as appropriate to the new function"""
        # return arg and whether it's a return val
        try:
            # argument is a type (indicating return val)
            return self.new_ptr(arg), True
        except KeyError:
            try:
                # argument is a Python value to convert
                return self.new_var(arg), False
            except KeyError:
                # argument is a Python value not to convert
                return arg, False
    
    def __init__(self, lib_filename, header_filename, out=print):
        """Wrap Andor-formatted DLLs for straightforward use in Python"""
        self.lib = cdll.LoadLibrary(lib_filename)
        
        # the map from numbers to #defined names
        consts = {} 
        # the map from #defined names that are errors to numbers
        errs = {}
        # syntax that Andor uses for #defined values in header files
        const_re = re.compile(r"((?:DRV|AC|SHAMROCK)_[A-Z0-9_]+?) ([0-9]+)")
        with open(header_filename) as f:
            for line in f:
                # Will be a list of tuples if line defines something, else None
                found_groups = const_re.findall(line)
                if found_groups:
                    name, num = found_groups[0]
                    # add name: num to consts
                    consts[name] = int(num)
                    if len(num) == 5:
                        # add num: name to errs, as long as it's a 5-digit num
                        errs[int(num)] = name
        
        self.consts = consts
        self.errs = errs
        self.out = out
        
    def __getattr__(self, name):
        """Get the improved function from the wrapped library

        This function is only called if `name` is not already in the instance
        `__dict__` or the class tree. Once foreign functions are called once,
        their improved versions are added to the instance `__dict__`, so
        __getattr__ is not called again.
        """
        # See if the DLL has the desired function. If not, raise a more
        # comprehensible AttributeError
        try:
            func = getattr(self.lib, name)
        except AttributeError:
            msg = "'AndorDLL' object has no attribute %r, and it was not found"\
                  "in external library %r" % (name, self.lib)
            raise AttributeError(msg)

        # Create and memorize the function before giving it to the user
        new_func = self.wrap(func, name)
        self.__dict__[name] = new_func
        return new_func
        
    def wrap(self, func, name):
        """Define and return the improved function"""
        def _new_func(*args):
            # Convert all arguments to get two iterables:
            #   new_args: the converted argument
            #   is_return_val: whether the corresponding argument will
            #       ultimately be returned
            # If there are no args, zip would return None, so instead define
            # them as empty iterables.
            if len(args) > 0:
                new_args, is_return_val = zip(*map(self.convert_arg, args))
            else:
                new_args, is_return_val = (), ()
            
            #print(str(func) + " \n")
            
            return_val = func(*new_args) # Call the function
            msg = self.errs[return_val] # Look up the return code
            if not "SUCCESS" in msg: raise IOError(msg)
            
            # return value: tuple of values of pointers passed as arguments
            # if just one pointer, return just its value
            # if no pointers, return None
            to_return = []
            for i, arg in enumerate(new_args):
                if is_return_val[i]:
                    try:
                        # byref(c_int, c_long, c_float)
                        to_return.append(arg._obj.value)
                    except AttributeError:
                        # c_char_p
                        to_return.append(arg.value)
                
            # What to do depends on return value. If none, print SUCCESS.
            # Otherwise, just return the value.
            if len(to_return) == 0:
                self.out(msg)
            elif len(to_return) == 1:
                return to_return[0]
            else:
                return tuple(to_return)

        # Make the function easier to recognize before returning it
        _new_func.func_name = name
        _new_func.func_doc = "Wrapped function %s from %s" % (name,
            self.lib)
        return _new_func

class QAndorDLL(QAndorObject, AndorDLL):
    """Wrapped version of AndorDLL that implements one PyQt signal"""

    def __init__(self, lib_filename, header_filename, out=None):
        QAndorObject.__init__(self)
        AndorDLL.__init__(self, lib_filename, header_filename, out=out)

    def __getattr__(self, name):
        return AndorDLL.__getattr__(self, name)

# Predefine DLLs based on given filenames
# Which DLL to use depends on architecture:
bitness = platform.architecture()[0]
dlls = dlls_64 if bitness == "64bit" else dlls_32

# Add the DLLs to this scope for importing
for varname, (subdir, dll, header) in dlls.items():
    locals().update(
        {varname: _andor_exec(QAndorDLL, args=(dll, header), subdir=subdir)}
        )