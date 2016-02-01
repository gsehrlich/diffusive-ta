from PyQt4 import QtCore
import atexit

class QAndorObject(QtCore.QObject):
    """Wrapped version of an Andor interface that implements PyQt signals.

    This object:
    * lives in its own QThread, which it automatically creates, starts,
    and quits;
    * can be initialized with an optional "out" function as a kwarg so that,
    when `obj.out(msg)` is called, will first emit `obj.message` with `msg`
    as an argument, and then call the provided function."""
    message = QtCore.pyqtSignal(str)

    def __init__(self, out=None):
        """`out` should be a print-style function: fn(s, sep=" ", end="\\n").
        Currently no support is provided for a `file` kwarg."""
        QtCore.QObject.__init__(self)
        self.out = out

        # Automate thread creation, starting, and deletion
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