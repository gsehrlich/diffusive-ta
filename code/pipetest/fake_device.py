class FakeDevice(object):
    def __init__(self):
        self.s = ""

    def write(self, s):
        self.s += s
        print s
        return long(len(self.s))

    def readall(self):
        to_return = self.s
        self.s = ""
        return to_return