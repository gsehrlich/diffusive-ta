from ._andorpath import _self_path
import os
import re

def _parse(filename):
    """Return a dict of known serial numbers : variable names"""
    # create re for parsing and dict for storing
    regex = re.compile(r"(\w+): (\w+)$", flags=re.MULTILINE)
    known = {}

    # parse the file from the package directory
    with open(os.path.join(_self_path, filename)) as f:
        for line in f:
            m = regex.match(line)
            if m:
                g = m.groups()
                known[g[0]] = g[1]

    return known

# put the dicts in this scope for easy importing
spectrometers = _parse("spectrometers.txt")
cameras = _parse("cameras.txt")