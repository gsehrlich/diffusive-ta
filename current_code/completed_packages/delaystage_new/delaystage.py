
import sys
import serial
from PyQt4 import uic
from PyQt4.QtGui import QWidget, QApplication
from PyQt4.QtCore import QObject, QCoreApplication, SIGNAL, pyqtSignal, pyqtSlot, QThread
from time import sleep
import WorkerThread as thread

# gehrlich for debugging
import os




class DelayStage(QObject):
    throwMessage = pyqtSignal(str, int, name='throwMessage')
    moveFinished = pyqtSignal(float,name='moveFinished')


    def __init__(self,widget):
        QObject.__init__(self)
        self.parent=widget
        self.ser=serial.Serial()
        self.mutex=QtCore.QMutex(mode =QtCore.QMutex.Recursive)
        self.moveThread=thread.WorkerThread()
        self.moveThread.canDropJobs=True

             
    def _initalize(self):
        if self.parent.ledDelayStage.isChecked():
            self.ser.close()
            self.parent.ledDelayStage.setChecked(False)
            self.throwMessage.emit("delaystage was disconnected",0)
        else:
            self.throwMessage.emit("Initialize delaystage:",0)
            self.ser.port="COM%d" % self.parent.ComPort.value()
            self.ser.baudrate=57600
            self.ser.parity=serial.PARITY_NONE
            self.ser.stopbits=1
            self.ser.bytesize=8
            self.ser.xonxoff = True
            self.ser.timeout=1
            if not self.ser.isOpen():
                self.ser.open()
            if self.ser.isOpen():
                s = self.getInfo("1ID?")
                print "%r" % s
                if "FMS300PP" in s:
                    self.throwMessage.emit("--> Motor activated",2)
                    self.parent.motorPosition.setValue(self.getPosition())
                    self.moveFinished.emit(self.getPosition())
                    self.parent.ledDelayStage.setChecked(True)
                else:
                    self.throwMessage.emit("--> Error: delaystage Motor could not be activated!",2)
                    self.throwMessage.emit("--> Wrong Portnumber for the delaystage?",2)

            else:
               self.throwMessage.emit("--> Error: Comport could not be opend!",2)

    def updateStageposition(self,value):
        lock=QtCore.QMutexLocker(self.mutex)
        self.parent.motorPosition.setValue(value)
    def toggleMoveLed(self,status):
        lock=QtCore.QMutexLocker(self.mutex)
        self.parent.labelMotorActive.setEnabled(status)
        #self.parent.ledMotion.setChecked(status)
    def sendCommand(self,text):
        lock=QtCore.QMutexLocker(self.mutex)
        self.ser.write(text+"\r\n")
    def getInfo(self,request):
        lock=QtCore.QMutexLocker(self.mutex)
        self.sendCommand(request)
        return self.ser.readline()[len(request)-1:]
    def getPosition(self):
        return(float(self.getInfo("1TP?")))
    def getVelocity(self):
        return(float(self.getInfo("1VA?")))
    def isMoving(self):
        lock=QtCore.QMutexLocker(self.mutex)
        controller_state = self.getInfo("1TS?")[-4:-2]
        return (controller_state in ("1E", "1F", "28"))
    def moveAction(self):
        lock=QtCore.QMutexLocker(self.mutex)
        self.parent.labelMotorActive.setEnabled(True)
        #self.parent.ledMotion.setChecked(True)
        lock.unlock()
        while self.isMoving():
            self.parent.motorPosition.setValue(self.getPosition())
            sleep(0.1)
        lock.relock()
        newPosition=self.getPosition()
        self.parent.motorPosition.setValue(newPosition)
        #self.parent.ledMotion.setChecked(False)
        self.parent.labelMotorActive.setEnabled(False)
        self.moveFinished.emit(newPosition)
        return
    def stopMotion(self):
        lock=QtCore.QMutexLocker(self.mutex)
        self.sendCommand("1ST")
    def goToPosition(self,position,wait=False):
        self.sendCommand("1PA%1f"%position)
        if wait:
            self.moveAction()
        else:
            self.moveThread.executeFunction(self.moveAction)
    def moveRelative(self,position,wait=False):
        self.sendCommand("1PR%1f"%position)
        if wait:
            self.moveAction()
        else:
            self.moveThread.executeFunction(self.moveAction)
    def sendMessage(self,msg):
        answer=str(self.getInfo(msg))
        if answer=="":
            return("The device has not answered")
        return answer
    def getErrorMsg(self):
        return(self.getInfo("TB?"))
    def setVelocity(self,value):
         self.sendCommand("1VA%1f"%value)
    def redefinePosition(self,newValue):
        lock=QtCore.QMutexLocker(self.mutex)
        self.sendCommand("1DH%1f"%newValue)
        self.parent.motorPosition.setValue(self.getPosition())



            
            
           
        

        
class DelayStageWidget(QWidget):
    initialize = pyqtSignal(name='initalize DelayStage')
    initialize = pyqtSignal(name='initalize DelayStage')
    goToPosition = pyqtSignal(float,name='initalize DelayStage')


    def __init__(self,parent=None):
        QWidget.__init__(self,parent)
        print os.getcwd()
        self.ui=uic.loadUi(os.path.join(os.path.dirname(__file__),"DelayStage.ui"),self)
        self.delaystage=DelayStage(self)
        

    @pyqtSlot() 
    def on_BAbsolutePosition_clicked(self):
         if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Send delaystage to: "+str(self.AbsolutePosition.value()),0)
            self.delaystage.goToPosition(self.AbsolutePosition.value())
    @pyqtSlot()
    def on_BRelativePosition_clicked(self):
        if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Shift delaystage for: "+str(self.relativePosition.value())+" mm",0)
            self.delaystage.moveRelative(self.relativePosition.value())
    @pyqtSlot()
    def on_BSetVelocity_clicked(self):
          if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Set velocity of delaystage to: "+str(self.velocity.value()),0)
            self.delaystage.setVelocity(self.velocity.value())
    @pyqtSlot()
    def on_BSendCommand_clicked(self):
        if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Send to delaystage: "+self.sendCommand.text(),0)
            self.delaystage.throwMessage.emit(self.delaystage.sendMessage(str(self.sendCommand.text())),0)
    @pyqtSlot()
    def on_BRedefinePosition_clicked(self):
        if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Redefine current Position to: "+str(self.redefinePosition.value()),0)
            self.delaystage.redefinePosition(self.redefinePosition.value())
    @pyqtSlot()
    def on_BDelayStageError_clicked(self):
        if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Request last Error message:",0)
            self.delaystage.throwMessage.emit("--> "+self.delaystage.getErrorMsg(),1)
    @pyqtSlot()
    def on_BStopMotion_clicked(self):
        if self.ledDelayStage.isChecked():
            self.delaystage.throwMessage.emit("Stop movement of delaystage:",0)
            self.delaystage.stopMotion()
    @pyqtSlot()     
    def on_BDelaystageConnect_clicked(self):
        self.delaystage._initalize()
        self.velocity.setValue(self.delaystage.getVelocity())
            



from PyQt4.QtGui import QDockWidget, QMainWindow, QSizePolicy
from PyQt4.QtCore import Qt
from PyQt4 import QtCore
class LabControl(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        #self.ui=uic.loadUi("mainwindow.ui",self)
        self.DelayStageDock=QDockWidget("DelayStage",self)
        self.DelayStageDock.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        self.DelayStageDock.setWidget(DelayStageWidget(self))
        self.DelayStageDock.widget().setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        self.addDockWidget(Qt.TopDockWidgetArea,self.DelayStageDock)

        self.DelayStageDock.widget().delaystage.throwMessage.connect(self.getMessage)
        
    def on_actionDelayStage_triggered(self):
        self.close()

    def getMessage(self,text,level):
        print(text)






if __name__ == '__main__':
    app = QApplication(sys.argv)
    labControl=LabControl()
    labControl.show()


    sys.exit(app.exec_())

