from PyQt4 import QtCore
import atexit

class QAndorObject(QtCore.QObject):
    """Wrapped version of an Andor interface that implements PyQt signals"""
    message = QtCore.pyqtSignal(str)

    def __init__(self, out=None):
        QtCore.QObject.__init__(self)
        self.out = out

        self.thread = QtCore.QThread()
        self.moveToThread(self.thread)
        QtCore.QTimer.singleShot(0, self.thread.start)
        self.thread.started.connect(self.make_running)
        self.running = False
        atexit.register(self.atexit)

    def make_running(self):
        self.running = True

    @property
    def out(self):
        """Make `out` refer to the function that also emits the signal"""
        return self.signal_out
    @out.setter
    def out(self, val):
        """Store the function itself in an auxiliary variable"""
        self._out = val

    def signal_out(self, *args, **kwargs):
        """Emit the message before writing to the desired stream"""
        sep = kwargs.pop("sep", " ")
        end = kwargs.pop("end", "\n")
        if len(kwargs) > 0:
            template = "signal_out() got an unexpected keyword argument: %r"
            raise TypeError(template % kwargs.keys()[0])
        self.message.emit(sep.join(args) + end)
        if self._out is not None:
            self._out(*args, sep=sep, end=end)

    def atexit(self):
        if self.running:
            self.__del__()

    def __del__(self):
        self.thread.quit()