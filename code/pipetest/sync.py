from PyQt4 import QtCore
import time
import datetime

class SyncDaemon(QtCore.QThread):
    def __init__(self):
        super(SyncDaemon, self).__init__()
        self.daemon = True
        self.synced = []

    def _debug_print(self, s, mode='a+'):
        with open('synclog.txt', mode) as f:
            f.write("%s\n" % s)

    def sync(self, getter1, getter2, setter2):
        self.synced.append((getter1, getter2, setter2))

    def run(self):
        while True:
            time.sleep(0.1)
            for getter1, getter2, setter2 in self.synced:
                val = getter1()
                if val != getter2():
                    setter2(val)