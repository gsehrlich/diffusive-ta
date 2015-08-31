
import sys
import serial
# gehrlich not used import Daniel
from PyQt4 import uic
from PyQt4.QtGui import QWidget, QApplication
from PyQt4.QtCore import QObject, QCoreApplication, SIGNAL, pyqtSignal, pyqtSlot, QThread
from time import sleep
# gehrlich not used from Daniel import WorkerThread as thread

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
        # gehrlich not used self.moveThread=thread.WorkerThread()
        # gehrlich not used self.moveThread.canDropJobs=True

             
    def _initalize(self):
        if self.parent.ledDelayStage.isChecked():
            self.ser.close()
            self.parent.ledDelayStage.setChecked(False)
            self.throwMessage.emit("delaystage was disconnected",0)
        else:
            self.throwMessage.emit("Initialize delaystage:",0)
            self.ser.port=int(self.parent.ComPort.value()-1)
            self.ser.baudrate=19200
            self.ser.parity='N'
            self.ser.stopbits=1
            self.ser. bytesize=8
            self.ser.timeout=1
            if not self.ser.isOpen():
                self.ser.open()
            if self.ser.isOpen():
                self.sendCommand("1MO")
                if self.getInfo("1MO?"):
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
        self.parent.ledMotion.setChecked(status)
    def sendCommand(self,text):
        lock=QtCore.QMutexLocker(self.mutex)
        self.ser.write((text+"\r").encode())
    def getInfo(self,request):
        lock=QtCore.QMutexLocker(self.mutex)
        self.sendCommand(request)
        return(self.ser.readline())
    def getPosition(self):
        return(float(self.getInfo("1TP?")))
    def isMoving(self):
        lock=QtCore.QMutexLocker(self.mutex)
        return(not int(self.getInfo("1MD")))
    def moveAction(self):
        lock=QtCore.QMutexLocker(self.mutex)
        self.parent.ledMotion.setChecked(True)
        lock.unlock()
        while self.isMoving():
            self.parent.motorPosition.setValue(self.getPosition())
            sleep(0.1)
        lock.relock()
        newPosition=self.getPosition()
        self.parent.motorPosition.setValue(newPosition)
        self.parent.ledMotion.setChecked(False)
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
            self.MoveThread.executeFunction(self.moveAction)
    def moveRelative(self,position,wait=False):
        self.sendCommand("1PR%1f"%position)
        if wait:
            self.moveAction()
        else:
            self.MoveThread.executeFunction(self.moveAction)
    def sendMessage(self,msg):
        answer=str(self.getInfo(msg))
        if answer=="":
            return("The device has not answerd")
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
        self.ui=uic.loadUi("DelayStage.ui",self)
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
            self.delaystage.throwMessage.emit(self.delaystage.sendMessage(self.sendCommand.text()),0)
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

