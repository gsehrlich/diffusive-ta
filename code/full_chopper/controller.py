from PyQt4 import QtCore
import multiprocessing
import serial
import time
import _winreg as winreg
import itertools

class ChopperController(QtCore.QObject):
    start = QtCore.pyqtSignal(name="start")
    to_chopper = QtCore.pyqtSignal(str, name="toChopper")
    from_chopper = QtCore.pyqtSignal(str, name="fromChopper")

    def __init__(self):
        super(ChopperController, self).__init__()

        self.thread = QtCore.QThread()
        self.thread.start()
        self.moveToThread(self.thread)

        self.pipe, _pipe_serial = multiprocessing.Pipe()
        self.serial_process = ChopperProcess(_pipe_serial)

        self.start.connect(self.run)
        self.to_chopper.connect(self.pipe.send)

    @QtCore.pyqtSlot(str)
    def run(self):
        self.serial_process.start()

        while True:
            if self.pipe.poll():
                self.from_chopper.emit(self.pipe.recv())
            time.sleep(0.01)

class ChopperProcess(multiprocessing.Process):
    def __init__(self, pipe_connection):
        super(ChopperProcess, self).__init__()
        self.pipe = pipe_connection
        self.daemon = True

    # from http://stackoverflow.com/questions/1205383/
    # listing-serial-com-ports-on-windows
    @staticmethod
    def _enumerate_serial_ports():
        """ Uses the Win32 registry to return a iterator of serial 
            (COM) ports existing on this computer.
        """
        path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        except WindowsError:
            raise IterationError

        for i in itertools.count():
            try:
                val = winreg.EnumValue(key, i)
                yield (str(val[1]), str(val[0]))
            except EnvironmentError:
                break

    def run(self):
        for port_name, _ in self._enumerate_serial_ports():
            device = serial.Serial(port=port_name, timeout=1, baudrate=115200)
            device.write('id?\r')
            time.sleep(1)
            s = device.readall()
            print s
            if "MC2000" in s:
                self.chopper = device
                break
        else:
            raise IOError("Chopper not found")

        while True:
            if self.pipe.poll():
                self.chopper.write(str(self.pipe.recv()) + '\r')
            s = self.chopper.readall()
            if len(s) > 0:
                self.pipe.send(s.replace('\r', '\n'))
            time.sleep(0.01)