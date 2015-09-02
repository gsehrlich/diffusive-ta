from PyQt4 import QtGui, QtCore
import time

class SillyThread(QtCore.QThread):
    def run(self):
        time.sleep(5)

        super(SillyThread, self).run()

class SlotTester(QtGui.QWidget):
    call_slot = QtCore.pyqtSignal()
    call_nonslot = QtCore.pyqtSignal()

    def __init__(self):
        super(SlotTester, self).__init__()

        self.remote_obj = RemoteObject()
        print "RemoteObject created in thread %r" % QtCore.QThread.currentThread()

        self.worker = SillyThread()
        self.remote_obj.moveToThread(self.worker)
        print "RemoteObject moved to thread %r" % self.worker
        print "Now current thread is %r" % QtCore.QThread.currentThread()
        self.worker.started.connect(self.remote_obj.start_calls_this)
        self.worker.finished.connect(self.notify_finished)
        self.worker.start()

        self.slot_other_button = QtGui.QPushButton()
        self.slot_other_button.setText("Slot from object's thread")
        self.slot_other_button.clicked.connect(self.remote_obj.slot)

        self.nonslot_other_button = QtGui.QPushButton(self)
        self.nonslot_other_button.setText("Nonslot from object's thread")
        self.nonslot_other_button.clicked.connect(self.remote_obj.nonslot)

        self.slot_this_button = QtGui.QPushButton(self)
        self.slot_this_button.setText("Slot from this thread")
        self.slot_this_button.clicked.connect(self.remote_obj.slot)
        self.call_slot.connect(self.remote_obj.slot)

        self.nonslot_this_button = QtGui.QPushButton(self)
        self.nonslot_this_button.setText("Nonslot from this thread")
        self.nonslot_this_button.clicked.connect(self.remote_obj.nonslot)
        self.call_nonslot.connect(self.remote_obj.nonslot)

        self.slot_other_queued_button = QtGui.QPushButton(self)
        self.slot_other_queued_button.setText("Queued connection to slot from object's thread")
        self.slot_other_queued_button.clicked.connect(
            self.remote_obj.slot,
            type=QtCore.Qt.QueuedConnection
            )

        self.grid = QtGui.QGridLayout(self)
        self.grid.addWidget(self.slot_other_button)
        self.grid.addWidget(self.nonslot_other_button)
        self.grid.addWidget(self.slot_this_button)
        self.grid.addWidget(self.nonslot_this_button)
        self.grid.addWidget(self.slot_other_queued_button)

    def notify_finished(self):
        print "thread %r finished" % self.worker

class RemoteObject(QtCore.QObject):
    @QtCore.pyqtSlot()
    def slot(self):
        print "Slot called in thread %r" % QtCore.QThread.currentThread()
        self.print_thread()

    def nonslot(self):
        print "Nonslot called in thread %r" % QtCore.QThread.currentThread()
        self.print_thread()

    @QtCore.pyqtSlot()
    def start_calls_this(self):
        print "Start called in thread %r" % QtCore.QThread.currentThread()
        self.print_thread()

    def print_thread(self):
        print "I am in thread %r" % self.thread()

if __name__ == "__main__":
    app = QtGui.QApplication([])
    w = SlotTester()
    w.show()
    app.exec_()