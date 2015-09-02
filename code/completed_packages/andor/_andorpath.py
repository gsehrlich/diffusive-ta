"""Do stuff from within the Andor SDK installation directory."""

import os
import re

_importer_path = os.getcwd()
_self_path = os.path.dirname(__file__)

# Load the Andor SDK installation directory from file
def _get_andor_path():
    """Load the Andor SDK installation directory from file"""
    with open(os.path.join(_self_path, 'config.txt')) as f:
        s = f.read()
    # Parse the file contents and return just the path
    return re.match(r"andorpath: (.+)$", s, flags=re.MULTILINE).groups()[0]

def _andor_exec(func, args=None, kwargs=None, subdir=''):
    """Execute a function from within the Andor SDK installation directory"""
    andorpath = _get_andor_path()
    os.chdir(os.path.join(andorpath, subdir))

    # Set defaults and call function
    if args is None: args = ()
    if kwargs is None: kwargs = {}
    to_return = func(*args, **kwargs)

    # Change back before returning so that users aren't confused
    os.chdir(_importer_path)
    return to_return