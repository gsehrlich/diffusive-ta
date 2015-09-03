from ._andorpath import _self_path
import os
import re

def _parse(filename, regex=None):
    """Return a dict of known serial numbers : variable names (or specify)"""
    # create re for parsing and dict for storing
    if regex == None:
        regex = re.compile(r"(\w+): (\w+)$", flags=re.MULTILINE)
    known = {}

    # parse the file from the package directory
    with open(os.path.join(_self_path, filename)) as f:
        for line in f:
            m = regex.match(line)
            if m:
                g = m.groups()
                # if regex has two groups, do {first: second}.
                # otherwise, do {first: (second, third, fourth,...)}.
                known[g[0]] = g[1] if len(g) <= 2 else g[1:]

    return known

def _parse_dlls(filename):
    r"""Parse the DLLs specially. Format is same but info is different

    Format per line is:
        variable_name:\tsubdir_of_SDK\tdll_filename\theader_filename
    """
    # create a regex and pass it to already-defined _parse
    regex = re.compile(r"(\w+):\t([A-Za-z0-9._ -]+)\t([A-Za-z0-9._ -]+)"
                       r"\t([A-Za-z0-9._ -]+)$")
    
    return _parse(filename, regex)



# put the dicts in this scope for easy importing
spectrometers = _parse("spectrometers.txt")
cameras = _parse("cameras.txt")
dlls_32 = _parse_dlls("dlls_32.txt")
dlls_64 = _parse_dlls("dlls_64.txt")