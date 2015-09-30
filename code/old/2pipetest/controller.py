from PyQt4 import QtCore
import multiprocessing
import serial
import time

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

    def run(self):
        self.chopper = serial.Serial(port="COM3", baudrate=115200, timeout=1)

        while True:
            if self.pipe.poll():
                self.chopper.write(str(self.pipe.recv()) + '\r')
            s = self.chopper.readall()
            if len(s) > 0:
                self.pipe.send(s.replace('\r', '\n'))
            time.sleep(0.01)