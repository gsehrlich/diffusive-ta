# http://stackoverflow.com/questions/20324804/
# how-to-use-qthread-correctly-in-pyqt-with-movetothread

import sys
from PyQt4 import QtCore, QtGui
import time

class GenericWorker(QtCore.QObject):
    blerp = QtCore.pyqtSignal(str)
    bloop = QtCore.pyqtSignal()

    def __init__(self):
        super(GenericWorker, self).__init__()
        self.blerp.connect(self.run)
        self.bloop.connect(self.print_stuff)

    @QtCore.pyqtSlot(str)
    def run(self, some_string_arg):
        print some_string_arg

    @QtCore.pyqtSlot()
    def print_stuff(self):
        while True:
            print "?!"
            time.sleep(1.5)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    my_thread = QtCore.QThread()
    my_thread.start()

    # This causes my_worker.run() to eventually execute in my_thread:
    my_worker = GenericWorker()
    my_worker.moveToThread(my_thread)
    my_worker.blerp.emit("hello")
    my_worker.bloop.emit()

    time.sleep(5)

    print "starting"

    sys.exit(app.exec_())