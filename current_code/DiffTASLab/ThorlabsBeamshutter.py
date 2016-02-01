import sys
from PyQt4 import uic
from PyQt4.QtGui import QWidget, QApplication,QSizePolicy
from PyQt4.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QThread,QMutex,QMutexLocker
import ctypes
import datetime
from contextlib import contextmanager
#gehrlich different temp file structure from Daniel.WorkerThread import WorkerThread
from WorkerThread import WorkerThread

from PyQt4 import QAxContainer


class Beamshutter(QObject):
    throwMessage = pyqtSignal(str, int, name='throwMessage')
    CtrlStarted=pyqtSignal(bool,name="ControlStarted")
    enableShutter=pyqtSignal(int,name='EnableShutter')
    disableShutter=pyqtSignal(int,name='DisableShutter')
    setOpMode=pyqtSignal(int,int,name='setOpMode')
    setCyMode=pyqtSignal(int,float,float,int,name='SetCycleMode')
    getShutState=pyqtSignal(int,int,name='ShutterState')
    startControl=pyqtSignal(name='startControl')
    stopControl=pyqtSignal(name='stopControl')



    def __init__(self,widget):
        QObject.__init__(self)
        self.parent=widget
        self.beamshutter_not_found=False

        # gehrlich temporarily connect to another function for testing
        self.startControl.connect(self.do_something)
        self.stopControl.connect(self.do_something)
        self.CtrlStarted.connect(self.do_something)
        self.enableShutter.connect(self.do_something)
        self.disableShutter.connect(self.do_something)
        self.setOpMode.connect(self.do_something)
        self.setCyMode.connect(self.do_something)
        self.getShutState.connect(self.do_something)
        
        #try:
        """
        self.startControl.connect(self.parent.control.StartCtrl)
        self.stopControl.connect(self.parent.control.StopCtrl)
        self.CtrlStarted.connect(self.parent.control.GetCtrlStarted)
        self.enableShutter.connect(self.parent.control.SC_Enable)
        self.disableShutter.connect(self.parent.control.SC_Disable)
        self.setOpMode.connect(self.parent.control.SC_SetOperatingMode)
        self.setCyMode.connect(self.parent.control.SC_SetCycleParams)
        self.getShutState.connect(self.parent.control.SC_GetOPState)
        self.parent.control.MoveComplete.connect(self.stateChanged)
        """

        #except(AttributeError):
        #    self.throwMessage.emit("Beamshutter is not installed",0)
       #     self.beamshutter_not_found=True

    # gehrlich temporary fn to which to connect, so that I can test the UI
    def do_something():
        print "Beamshutter was told to do something"

    def initialize(self):
        self.startControl.emit()
        self.jobFinished()

    def finalize(self):
        self.stopControl.emit()
        self.jobFinished()

    def isInitialized(self): #notWorking
        # print ("test")
        # a=ctypes.c_bool(True)
        # started=ctypes.pointer(a)
        # self.CtrlStarted.emit(bool(ctypes.byref(a)))
        # print (started)
        #started = QVariant(1)
        #args=[started]
        #self.parent.control.dynamicCall("GetCtrlStarted(bool&)",args)
        return(True)

    def stateChanged(self, channelId): #Is this working?
        print("BeamShutter State Changed?")

    def enable(self):
        self.enableShutter.emit(1)
        self.parent.currentShutterState.emit("Open")
        self.jobFinished()
    def disable(self):
        self.disableShutter.emit(1)
        self.parent.currentShutterState.emit("Close")
        self.jobFinished()
    def getShutterState(self):
        result=ctypes.c_int(-1)
        self.getShutState.emit(1,ctypes.byref(result))
        self.jobFinished()
        return result.value

    def setOperationMode(self,mode):
        self.setOpMode.emit(mode)
        self.jobFinished()
    def setCycleParameters(self,onTime,offTime,numberOfCycles):
        self.setCyMode.emit(1,onTime,offTime,numberOfCycles)
        self.jobFinished()
    def jobFinished(self):
        lock=QMutexLocker(self.parent.mutex)
        self.parent.shutterReplied=True





class BeamshutterWidget(QWidget):
    currentShutterState=pyqtSignal(str,name='currentShutterState')
    def __init__(self,parent=None):
        QWidget.__init__(self,parent)
        self.ui=uic.loadUi("Beamshutter.ui",self)
        self.control = QAxContainer.QAxWidget(self)
        self.control.setControl('{3CE35BF3-1E13-4D2C-8C0B-DEF6314420B3}')
        self.control.setProperty("HWSerialNum",85845031)
        self.control.setGeometry(0,0,600,400)
        self.mutex=QMutex(mode =QMutex.Recursive)
        self.shutterReplied=False


        self.shut=Beamshutter(self)
        self.worker=WorkerThread()

        self.ui.mainLayout.addWidget(self.control)

        self.layout().setAlignment(Qt.AlignCenter)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHeightForWidth(True)
        self.setSizePolicy(sizePolicy)


    def heightForWidth(self, width):
        return width*0.75
    @pyqtSlot()
    def on_BInitializeShutter_clicked(self):
        if not self.LEDShutter.isChecked():
            self.initialize()
        else:
            self.finalize()
    def initialize(self):
        with self.check(timeOut=10):
            self.worker.executeFunction(self.shut.initialize)
        self.ui.LEDShutter.setChecked(True)


    def finalize(self):
        with self.check():
            self.worker.executeFunction(self.shut.finalize)
        self.LEDShutter.setChecked(False)


    def enable(self):
        with self.check():
            self.worker.executeFunction(self.shut.enable)

    def disable(self):
        with self.check():
            self.worker.executeFunction(self.shut.disable)

    def _del(self):
        if self.ui.LEDShutter.isChecked():
            self.finalize()

    def heightForWidth(self,w):
        return(w)

    @contextmanager
    def check(self,timeOut=2):
        out=datetime.datetime.now()+datetime.timedelta(seconds=timeOut)
        self.shutterReplied=shutterReplied=False
        yield
        while  datetime.datetime.now()<out and shutterReplied==False:
            self.mutex.lock()
            shutterReplied=self.shutterReplied
            self.mutex.unlock()

        if shutterReplied==False:
            raise Exception("ThorlabsShutter timed out and might be Crashed")



if __name__=="__main__":
    app = QApplication(sys.argv)
    shutter=BeamshutterWidget()
    shutter.show()
    sys.exit(app.exec_())
