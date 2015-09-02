from PyQt4.QtCore import QTimer, QThread, QObject, pyqtSignal
from PyQt4.QtGui import QApplication, QWidget, QPushButton

class Stopper(QObject):
    start_timer = pyqtSignal()
    stop_timer = pyqtSignal()

    def __init__(self):
        super(Stopper, self).__init__()

        print "current thread 2 %r" % QThread.currentThread()
        self.timer = QTimer()
        self.thread_of_timer = self.timer.thread()
        print "stopper.timer thread: %r" % self.thread_of_timer
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.prnt_msg)
        self.start_timer.connect(self.start)
        self.stop_timer.connect(self.stop)

    def start(self):
        print "starting"
        self.timer.start()

    def stop(self):
        print "stopping"
        print QThread.currentThread()
        print self.thread()
        print self.timer.thread()
        print "Timer thread has changed: %s" % (self.thread_of_timer is self.timer.thread())
        self.timer.stop()

    def prnt_msg(self):
        print "timer running"

class StopperWidget(QWidget):
    def __init__(self):
        super(QWidget, self).__init__()

        self.stopper = Stopper()
        self.timer_thread = QThread()
        print "w.timer_thread: %r" % self.timer_thread
        self.timer_thread.start()
        self.stopper.moveToThread(self.timer_thread)
        self.stopper.start_timer.emit()

        self.button = QPushButton(self)
        self.button.setText("Stop timer")
        self.button.clicked.connect(self.stopper.stop_timer)

    def __del__(self):
        print QThread.currentThread()
        print self.thread()
        print self.timer_thread
        self.stopper.stop_timer.emit()


app = QApplication([])
print "current thread: %r" % QThread.currentThread()
w = StopperWidget()
w.show()
app.exec_()