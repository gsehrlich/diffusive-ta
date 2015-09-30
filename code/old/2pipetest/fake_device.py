class Serial(object):
    def __init__(self, *args, **kwargs):
        self.s = ""

    def write(self, s):
        self.s += s
        return long(len(self.s))

    def readall(self):
        to_return = self.s
        self.s = ""
        return to_return