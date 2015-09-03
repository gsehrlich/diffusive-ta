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
    """Parse the DLLs specially. Format is same but info is different

    Format per line is:
        variable_name:\tsubdir_of_SDK\tdll_filename\theader_filename
    """
    # create a regex and pass it to already-defined _parse
    regex = re.compile(r"(\w+):\t([A-Za-z0-9._ -]+)\t([A-Za-z0-9._ -]+)"
                       r"\t([A-Za-z0-9._ -]+)$")
    return _parse(filename, regex)

def _parse_cam_info(filename):
    """Parse the cam info specially: Format is same but info is different"""
    # create a regex and pass it to already-defined _parse
    regex = re.compile(r"(\w+): port (\d), temp ([0-9-]+), index ([0-9]+)",
                        flags=re.MULTILINE)
    cam_info = _parse(filename, regex)

    # convert the tuple of strings to a dict of ints before returning the dict
    for cam_name in cam_info:
        port_str, temp_str, index_str = cam_info[cam_name]
        cam_info[cam_name] = {"port": int(port_str), "temp": int(temp_str),
                                "index": int(index_str)}
    return cam_info


# put the dicts in this scope for easy importing
spectrometers = _parse("spectrometers.txt")
cameras = _parse("cameras.txt")
dlls_32 = _parse_dlls("dlls_32.txt")
dlls_64 = _parse_dlls("dlls_64.txt")
cam_info = _parse_cam_info("cam_info.txt")

# camera serial numbers should be ints
cameras = {int(serial): cameras[serial] for serial in cameras}