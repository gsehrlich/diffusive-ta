# from http://pythonforengineers.com/your-first-gui-app-with-python-and-pyqt/

import sys
from PyQt4 import QtCore, QtGui, uic
import sync
import time
import multiprocessing, threading
import serial

from fake_device import FakeDevice

# Parse the Designer .ui file
UiWidget, QtBaseClass = uic.loadUiType("chopper.ui")

class ChopperControls(QtGui.QWidget, UiWidget):
    def __init__(self, *args, **kwargs):
        defaults = {"name": "Chopper"}
        defaults.update(kwargs)
        kwargs = defaults
        name = defaults.pop("name")
        self.controller = ChopperController()
        self.controller.start()
        self.pipe_listener = Listener(self.controller.pipe.poll, dt=0.1)
        self.pipe_listener.heard.connect(self.update_read_area)
        self.pipe_listener.start()

        QtGui.QWidget.__init__(self, *args, **kwargs)
        UiWidget.__init__(self)
        self.setupUi(self)
        self.setObjectName(name)

        # Set internal state at the beginning
        self.chopper_is_on = False
        self.freq = 100.
        self.editing = False

        # Connect widgets to methods
        self.on_button.clicked.connect(self.turn_chopper_on)
        self.off_button.clicked.connect(self.turn_chopper_off)
        self.freq_edit.returnPressed.connect(self.update_freq)
        self.freq_edit.textEdited.connect(self.text_edited)
        self.freq_edit.editingFinished.connect(self.editing_finished)

        # Create daemon to synchronize display with internal state
        # We'll start it after the window is shown
        self.sync_daemon = sync.SyncDaemon()

        # We will sync button states to internal on/off state
        sync_vals = [
            (self.is_chopper_on, self.on_button.isChecked, 
                self.on_button.setChecked),
            (self.is_chopper_off, self.off_button.isChecked,
                self.off_button.setChecked)
            ]
        # We'll also sync the text in the lineEdit to the internal freq state
        sync_vals.extend([
            (self.get_freq_str, self.freq_edit.text, self.set_freq_edit_text)
            ])

        # Sync everything
        for sync_val in sync_vals:
            self.sync_daemon.sync(*sync_val)

        # since sync_daemon is a Qthread, this will wait until the event loop
        # starts to start the daemon
        self.sync_daemon.start()

    #######
    # GETTERS AND SETTERS
    #######

    def is_chopper_on(self):
        return self.chopper_is_on

    def is_chopper_off(self):
        return not self.chopper_is_on

    def parse_lineEdit_freq(self):
        """
        try:
            val = float(self.freq_edit.text())
        except e:
            freq_edit.paletteChange(QtGui.QPalette(base=(255, 128, 128)))
        """
        return float(self.freq_edit.text())

    def get_freq_str(self):
        return "%d" % self.freq

    #####
    # FUNCTIONS CONNECTED TO WIDGETS
    #####

    def turn_chopper_on(self):
        self.chopper_is_on = True
        self.controller.pipe.send("enable=1")

    def turn_chopper_off(self):
        self.chopper_is_on = False
        self.controller.pipe.send("enable=0")

    def update_freq(self):
        self.freq = self.parse_lineEdit_freq()
        self.controller.pipe.send("freq=%s" % self.get_freq_str())

    def text_edited(self):
        self.editing = True

    def editing_finished(self):
        self.editing = False

    def update_read_area(self):
        self.read_area.appendPlainText(self.controller.pipe.recv())

    #####
    # OTHER FUNCTIONS?
    #####

    # this function isn't "connect"ed to a widget
    def set_freq_edit_text(self, s):
        if not self.editing:
            self.freq_edit.setText(s)

"""
class DeviceListener(QtCore.QThread):
    updated = QtCore.pyqtSignal()

    def __init__(self, dt, **kwargs):
        "Used by DeviceController."
        super(DeviceListener, self).__init__(**kwargs)
        self.update_stream = update_stream
        self.daemon = True
        self.dt = dt

        self.s = ""

    def run(self):
        while True:
            self.s += self.update_stream()
            time.sleep(self.dt)

    def view(self):
        return self.s

    def pop(self):
        s = self.s
        self.s = ""
        return s
"""

class DeviceController(multiprocessing.Process):
    def __init__(self, ListenerCls=None, device_args=(), device_connect=(),
        pipe_dt=0.1, device_dt=0.1, **kwargs):
        """Class in a separate process that connects a device to a pipe.

        Usage: override from_device/parent and do_also. Kwargs ``_pipe_dt`` and
        ``_device_dt`` will set how often the process checks pipe and device
        output; the rest are passed to ``multiprocessing.Process``."""
        self._pipe_dt = pipe_dt
        self._device_dt = device_dt

        super(DeviceController, self).__init__(name="DeviceController",
            **kwargs)

        self.pipe, self._pipe_int = multiprocessing.Pipe()
        self.daemon = True

        if callable(ListenerCls):
            self.ListenerCls = ListenerCls
            self.device_args = device_args
            self.device_connect = device_connect
        else:
            self.ListenerCls = Listener
            self.device_args = (self.device_has_output, 0.1)
            self.device_connect = None

    def run(self):
        #
        """
        self.device_listener = DeviceListener(self.device_has_output,
            dt=self._device_dt)
        self.device_listener.updated.connect(self.read_device)
        self.device_listener.start()
        """

        self.device_listener = self.ListenerCls(*self.device_args)
        self.device_listener.heard.connect(
            self.device_connect if self.device_connect is not None else
            lambda: self.from_device(self.read_device()))

        self.pipe_listener = Listener(self._pipe_int.poll, dt=0.1)
        print "about to connect"
        self.pipe_listener.heard.connect(print_and_call)
       #     lambda: self.from_parent(self._pipe_int.recv()))
        print "connected"

        self.device_listener.start()
        self.pipe_listener.start()

        self.main()

    ### MAIN FUNCTION
    def main(self):
        """Called after starting the listeners.

        Override to customize."""
        while True:
            time.sleep(100)

    ### FUNCTION FOR SENDING TO PIPE (already has poll and recv)
    def to_parent(self, obj):
        """Send object to this end of the pipe. No need to override."""
        self._pipe_int.send(obj)

    # FUNCTIONS FOR SENDING, LISTENING TO, AND RECEIVING FROM DEVICE
    def to_device(self, s):
        """Convenience method. Send s to device. Call from overriden methods.

        Override to set method for sending to device."""
        pass

    def device_has_output(self):
        """Return True if the device has output waiting.

        Override to customize."""
        return False

    def read_device(self):
        """Read the output from the device.

        Override to customize."""
        return ""

    # FUNCTIONS FOR RESPONDING TO INPUT FROM PIPE AND OUTPUT FROM DEVICE
    def from_parent(self, obj):
        """Receive recv from this end of the pipe and do something.

        Called when input is received from the pipe. Override this method to
        determine the behavior of controller on that input."""
        pass

    def from_device(self, s):
        """Receive s from device and do something.

        Called when input is received from the device. Override this method to
        determine how controller responds to device input."""
        pass

def print_and_call():
    derpaderp
    recv = self._pipe_int.recv()
    print "received %r" % recv
    self.from_parent(recv)

class ChopperControllerPlaceholder(DeviceController):
    def from_parent(self, recv):
        self.to_parent("Received object %r" % recv)

class ChopperController(DeviceController):
    def run(self):
        #self.chopper = serial.Serial(port="COM3", timeout=2, baudrate=115200)
        self.chopper = FakeDevice()
        self.to_device("verbose=1")

        # override what DeviceController.__init__ defaulted to
        self.ListenerCls = StreamingListener
        self.device_args = (self.chopper.readall, self._device_dt)
        self.device_connect = lambda: self.from_device(self.read_device())

        """
        # Continuously collect device output here and use it as a proxy
        # for the device itself.
        self.device_stream = ""
        self.device_stream_pos = 0
        self.device_streamer = threading.Thread(target=self.sync_device_stream)
        self.device_streamer.daemon = True
        self.device_streamer.start()
        """

        super(ChopperController, self).run()

    """
    def sync_device_stream(self):
        while True:
            self.device_stream += self.chopper.readall().replace("\r", "\n")
            time.sleep(0.1)
    """

    def to_device(self, s):
        self.chopper.write(s + "\r")

    """
    def device_has_output(self):
        return self.device_stream_pos < len(self.device_stream)
    """

    def read_device(self):
        return self.chopper_stream.readall()

    def from_parent(self, recv):
        self.to_device(recv)

    def from_device(self, s):
        print "called"
        self.to_parent(s)

class Listener(QtCore.QThread):
    # This the right place to put this because
    # http://stackoverflow.com/questions/2970312/
    # pyqt4-qtcore-pyqtsignal-object-has-no-attribute-connect
    heard = QtCore.pyqtSignal()

    def __init__(self, target=None, dt=1):
        """Call target with period dt. If True, emit heard."""
        super(Listener, self).__init__()
        self.daemon = True
        self.dt = dt

        # Keep target as a keyword argument and raise this error in __init__,
        # rather than making target a mandatory argument. This allows more
        # straightforward subclassing.
        if callable(target):
            self.target = target
        else:
            raise TypeError("Listener needs a callable target; "
                            "%r provided" % target)

    def run(self):
        while True:
            if self.target():
                print "heard something"
                self.heard.emit()
            time.sleep(self.dt)

class StreamingListener(Listener):
    def __init__(self, read_device=None, dt=0.1):
        super(StreamingListener, self).__init__(target=read_device, dt=dt)
        self.stream = ""
        self.pos = 0

    def run(self):
        while True:
            s = self.target()
            if len(s) > 0:
                self.heard.emit()
                self.stream += s
            time.sleep(self.dt)

    def readall(self):
        to_return = self.stream[self.pos:]
        self.pos = len(self.stream)
        return to_return


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = ChopperControls()
    window.show()
    sys.exit(app.exec_())