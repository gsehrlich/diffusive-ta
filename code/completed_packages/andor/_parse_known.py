from ._andorpath import _importer_path, _self_path
import os
import re

def parse():
    """Return a dict of known serial numbers : variable names"""
    # create re for parsing and dict for storing
    regex = re.compile(r"(\w+): (\w+)$", flags=re.MULTILINE)
    known = {}

    # move to the file directory and parse the file
    os.chdir(_self_path)
    with open('known.txt') as f:
        for line in f:
            m = regex.match(line)
            if m:
                g = m.groups()
                known[g[0]] = g[1]

    # move back to importing directory and return the dict
    os.chdir(_importer_path)
    return known