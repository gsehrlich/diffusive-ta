from PyQt4 import QtCore as core

class Worker(core.QThread):
    def run(self):
        print "just started running thread %r" % core.QThread.currentThread()
        print "I am thread %r" % self

        super(Worker, self).run()

def print_thread():
    print "currently in thread %r" % core.QThread.currentThread()

app = core.QCoreApplication([])
w = Worker()
w.started.connect(print_thread)
core.QTimer.singleShot(0, w.start)
app.exec_()