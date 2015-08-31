import threading
import time

class SyncDaemon(threading.Thread):
    def __init__(self):
        super(SyncDaemon, self).__init__()
        self.daemon = True
        self.synced = []

    def sync(self, getter1, getter2, setter2):
        self.synced.append((getter1, getter2, setter2))

    def run(self):
        while True:
            time.sleep(0.1)
            for getter1, getter2, setter2 in self.synced:
                val = getter1()
                if val != getter2():
                    setter2(val)