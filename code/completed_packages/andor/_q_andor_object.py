from PyQt4 import QtCore

class QAndorObject(QtCore.QObject):
    """Wrapped version of an Andor interface that implements PyQt signals"""
    message = QtCore.pyqtSignal(str)

    @property
    def out(self):
        """Make `out` refer to the function that also emits the signal"""
        return self.signal_out
    @out.setter
    def out(self, val):
        """Store the function itself in an auxiliary variable"""
        self._out = val

    def signal_out(self, sep=" ", end="\n", *args):
        """Emit the message before writing to the desired stream"""
        self.message.emit(sep.join(args) + end)
        if self._out is not None:
            self._out(*args, sep=sep, end=end)