# written by Daniel Tolksdorf
# with edits by Gabriel Ehrlich (gehrlich)

from pyqtgraph.Qt import QtGui
#from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal,QObject,pyqtSlot,SIGNAL,QThread,QMutexLocker
import numpy as np
import sys
#from Daniel import PlotBase
#from Daniel import DataStructure
import datetime

#import configurationWidget # from Daniel import configurationWidget
#import fileaccess # from Daniel import fileaccess
# gehrlich no hdf5plot from Daniel import EnergyConversion
import shutil
import os
#from Daniel.WorkerThread import WorkerThread
from pyqtgraph.dockarea import *


import time


class DataViewer(QtGui.QMainWindow):
    closed = pyqtSignal(name='closeEvent')

    def __init__(self,parent=None,name="DataViewer"):
        QtGui.QMainWindow.__init__(self,parent)
        self.setObjectName(name)
        self.parent=parent
        self.area = DockArea(self)
        self.area.setObjectName(name+"_DockWindow")
        self.setCentralWidget(self.area)
        self.resize(1000,500)
        # gehrlich 20150717: previously used dict():
        self.docks={"name": Dock(name)}
        self.setWindowTitle("Lab Control - Data Viewer")


    def closeEvent(self, event):
        self.closed.emit()

    def addWidget(self,name,Widget,Size=(50,50),position="right",relativeTo="None",minSize=(50,50),sizePolicy=(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)):
        dock=Dock(name,size=Size)
        dock.addWidget(Widget)
        dock.setMinimumSize(minSize[0],minSize[1])
        dock.setBaseSize(*minSize)
        dock.setSizePolicy(*sizePolicy)
        self.docks[name]=dock
        if relativeTo=="None":
           self.area.addDock(dock,position)
        else:
            self.area.addDock(dock,position,self.docks[relativeTo])
        return(Widget)


    def getDock(self,name):
        return(self.docks[name])



class DataHandler(QObject):
    sigUpdateGui=pyqtSignal(object)
    throwMessage = pyqtSignal(str, int, name='throwMessage')
    sigUpdateRequest=pyqtSignal(object)
    def __init__(self,config):
        QObject.__init__(self)
        self.dataSet=DataStructure.Dataset(self,config)
        self.dataSet.initialize()
        self.timeFilter=[None,None]
        self.guiUpdateTime=1
        self.updateTimer=QtCore.QTimer(self)
        #self.updateTimer.timeout.connect(self.updateGui)
        self.updateTimer.setSingleShot(True)
        self.mutex=QtCore.QMutex(mode =QtCore.QMutex.Recursive)
        self.sigUpdateRequest.connect(self.dataTransfer,QtCore.Qt.QueuedConnection)
        self.countrate=0
        self.selection=0
        self.electrons=np.empty(0, [("x", 'i2'), ("y", 'i2'), ("time", 'i4')])


    def __enter__(self):
        self.mutex.lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mutex.unlock()

    def updateGui(self):
        lock=QtCore.QMutexLocker(self.mutex)
        if self.updateTimer.isActive():
            ##! update Time not reached yet
            return False
        if self.update==False:
            ##! Data did not change
            return False
        ##! restart Update Timer and Process Events
        self.updateTimer.start(self.dataSet.config["Spectra/Gui Update Time (s)"]*1000)
        self.update=False
        ###Process Events in case that electrons are faster added then Processed
        QtCore.QCoreApplication.processEvents()

        if self.electrons.shape[0]!=0:
            if self.dataSet.config["File Configuration/Save raw data"]:
                self.dataSet.dumpRawData(self.electrons)

            self.dataSet.addElectrons(self.electrons)
            self.electrons=np.empty(0, [("x", 'i2'), ("y", 'i2'), ("time", 'i4')])
        self.dataTransfer(["all"])

    def configChanged(self,name,value):
        lock=QtCore.QMutexLocker(self.mutex)
        if name in self.dataSet.config:
            self.dataSet.config[name]=value


    def closeRawData(self):
        if self.dataSet.rawData!=None:
            self.dataSet.rawData.close()
            self.dataSet.rawData=None


    def dataTransfer(self, spectrum):
        lock=QtCore.QMutexLocker(self.mutex)
        transfer={}
        if "timeHistogram" in spectrum or "all" in spectrum:
            transfer["timeHistogram"]=(np.copy(self.dataSet.timeRange),np.copy(self.dataSet.timeHistogram))
        if "energyHistogram" in spectrum or "all" in spectrum:
            transfer["energyHistogram"]=(np.copy(self.dataSet.energyRange),np.copy(self.dataSet.energyHistogram))
        if "timeImage" in spectrum or "all" in spectrum:
            transfer["timeImage"]=np.copy(self.dataSet.timeImage)
        if "energyImage" in spectrum or "all" in spectrum:
            transfer["energyImage"]=np.copy(self.dataSet.energyImage)
        if "countrate" in spectrum or "all" in spectrum:
            transfer["countrate"]=(np.copy(self.dataSet.countrate.getData()["eventTime"]),np.copy(self.dataSet.countrate.getData()["events"]))
        if "keithley" in spectrum or "all" in spectrum:
            if self.dataSet.keithley!=None:
                transfer["keithley"]=(np.copy(self.dataSet.keithley.getData()["eventTime"]),np.copy(self.dataSet.keithley.getData()["events"]))
        if "liveView" in spectrum or "all" in spectrum:
            transfer["liveView"]=(np.copy(self.dataSet.mcp),self.countrate,self.selection)
        self.sigUpdateGui.emit(transfer)

    @QtCore.pyqtSlot(bool)
    def clearSpectra(self,rawData=True):
        lock=QtCore.QMutexLocker(self.mutex)
        QtCore.QCoreApplication.processEvents()
        self.dataSet.clearSpectra()
        self.electrons=np.empty(0, [("x", 'i2'), ("y", 'i2'), ("time", 'i4')])
        if rawData:
            self.closeRawData()
        self.sigUpdateRequest.emit(["all"])

    def addElectrons(self,electrons,time,keithley):
        lock=QtCore.QMutexLocker(self.mutex)
        self.update=True
        self.countrate=electrons.shape[0]/self.dataSet.config["Spectra/Exposure Time (s)"]
        if not self.timeFilter[0]==None and not self.timeFilter[1]==None:
            electrons = electrons[np.logical_and(electrons["time"] > self.timeFilter[0], electrons["time"] < self.timeFilter[1])]
        elif not self.timeFilter[0]==None:
            electrons = electrons[electrons["time"] > self.timeFilter[0]]
        elif not self.timeFilter[1]==None:
            electrons = electrons[electrons["time"] < self.timeFilter[1]]
        self.selection=electrons.shape[0]/self.dataSet.config["Spectra/Exposure Time (s)"]

        self.electrons=np.append(self.electrons,electrons)
        self.dataSet.countrate.append(time,electrons.shape[0])
        if keithley!=None:
            self.dataSet.keithley.append(time,keithley)
        self.updateGui()

    def rotationChanged(self):
        lock=QtCore.QMutexLocker(self.mutex)
        if not self.dataSet.rawData==None:
            electrons=self.dataSet.getElectronsFromRawData()
            self.dataSet.clearSpectra(ignoreCountrate=True)
            self.dataSet.setElectrons(electrons=electrons)
            self.dataTransfer(["All"])
    def finalize(self):
        lock=QtCore.QMutexLocker(self.mutex)
        self.updateTimer.stop()
        if self.dataSet.rawData!=None:
            self.dataSet.rawData.close()
            self.dataSet.rawData=None




class Measurement(QObject):
    throwMessage = pyqtSignal(str, int, name='throwMessage')
    sigSaveMeasurement = pyqtSignal(bool, name='save')
    updateWindows=pyqtSignal(str,name="updateView")
    sigUpdateCountrate=pyqtSignal(int,str)

    sigTest=pyqtSignal()

    def __init__(self,openFile=None,themisApp=None):
        QObject.__init__(self)
        self.themisApp=themisApp
        self.configWidget=configurationWidget.configurationWidget(self)
        self.config=self.configWidget.p
        self.DataThread=QThread(self)
        self.dataHandler=DataHandler(self.configWidget.toDict())
        self.dataHandler.moveToThread(self.DataThread)
        self.dataHandler.updateTimer.timeout.connect(self.dataHandler.updateGui)
        self.dataHandler.sigUpdateGui.connect(self.updateView,QtCore.Qt.QueuedConnection)
        self.configWidget.sigConfigChanged.connect(self.dataHandler.configChanged,QtCore.Qt.QueuedConnection)
        self.DataThread.start()


        self.viewer=DataViewer(name="Measurement")
        self.timeFilter=[None,None]
        self.acquisitionTime=-1



        #SetWindows
        self.viewer.addWidget("Control",self.configWidget,position="left",Size=(2,2),minSize=(250,250),sizePolicy=(QtGui.QSizePolicy.Fixed,QtGui.QSizePolicy.Fixed))
        self.timeImage=self.viewer.addWidget("Time Image",PlotBase.TimeImageWidget(self),position="right",relativeTo="Control",Size=(10,10),minSize=(300,250))
        self.energyImage=self.viewer.addWidget("Energy Image",PlotBase.EnergyImageWidget(self),position="below",relativeTo="Time Image",Size=(10,10),minSize=(300,250))
        self.countrate=self.viewer.addWidget("Countrate",PlotBase.CountrateWidget(),position="bottom",relativeTo="Time Image",Size=(10,10),minSize=(300,250))
        self.keithley=self.viewer.addWidget("Keithley",PlotBase.KeithleyWidget(),position="below",relativeTo="Countrate",Size=(10,10),minSize=(300,250))
        self.timeHistogram=self.viewer.addWidget("Time Histogram",PlotBase.TimeHistogramWidget(),position="right",relativeTo="Time Image",Size=(10,10),minSize=(300,250))
        self.energyHistogram=self.viewer.addWidget("Energy Histogram",PlotBase.EnergyHistogramWidget(self),position="below",relativeTo="Time Histogram",Size=(10,10),minSize=(300,250))

        if themisApp!=None:
            self.liveView=self.viewer.addWidget("MCP",PlotBase.LiveView(self),position="above",relativeTo="Time Image",Size=(10,10),minSize=(400,250))
            self.viewer.addWidget("Themis",self.themisApp,position="above",relativeTo="Control",Size=(10,10),minSize=(250,250))
            # Buttons=QtGui.QHBoxLayout()
            # self.start=QtGui.QPushButton("Start")
            # self.start.setIcon(QtGui.QIcon('Bilder/accept.png'))
            # #self.start.clicked.connect(self.startMeasurement)
            # Buttons.addWidget(self.start)
            # self.pause=QtGui.QPushButton("Pause")
            # self.pause.setIcon(QtGui.QIcon('Bilder/pause.png'))
            # #self.pause.clicked.connect(self.pauseMeasurement)
            # Buttons.addWidget(self.pause)
            # self.stop=QtGui.QPushButton("Stop")
            # self.stop.setIcon(QtGui.QIcon('Bilder/stop.png'))
            # #self.stop.clicked.connect(self.on_stop_clicked)
            # Buttons.addWidget(self.stop)
            # #self.configWidget.layout().insertWidget(0,Buttons)
        else:
            self.liveView=None #None#self.viewer.addWidget("MCP",PlotBase.LiveView(),position="above",relativeTo="Time Image",Size=(10,10),minSize=(400,250))

        if not openFile==None:
            self.loadMeasurement(openFile)
        self.initializeSignals()


    def finalize(self):
        self.dataHandler.finalize()
        self.dataHandler.deleteLater()
        del self.dataHandler
        self.DataThread.quit()
        self.DataThread.wait()
        #self.dataHandler.updateTimer.timeout.disconnect(self.dataHandler.updateGui)
        #self.dataHandler.sigUpdateGui.disconnect(self.updateView)
        #self.configWidget.sigConfigChanged.disconnect(self.dataHandler.configChanged,)
        #self.dataHandler.deleteLater()

    def initializeSignals(self):
        self.configWidget.connectSignal(self.config.param("Spectra","Time Histogram","Time min").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("Spectra","Time Histogram","Time max").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("Spectra","Time Histogram","Time resolution").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("Spectra","Time Image","Xbins").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("Spectra","Time Image","Ybins").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("Spectra","Rotate MCP").sigValueChanged,self.dataHandler.rotationChanged)
        self.configWidget.connectSignal(self.config.param("DLLParams","X Min").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("DLLParams","X Max").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("DLLParams","Y Min").sigValueChanged,self.timeConfigChanged)
        self.configWidget.connectSignal(self.config.param("DLLParams","Y Max").sigValueChanged,self.timeConfigChanged)


        self.configWidget.connectSignal(self.config.param('File Configuration', 'Save Measurement').sigActivated,self.saveMeasurement)
        self.configWidget.connectSignal(self.config.param('Spectra', 'Create new Conversion').sigActivated,self.createStandardConversion)


        self.sigSaveMeasurement.connect(self.saveMeasurement)
        self.timeHistogram.selectionChanged.connect(self.selectionChanged)




    def selectionChanged(self,min,max):
        with self.dataHandler:
            self.dataHandler.dataSet.timeImage.fill(0)
            electrons=self.dataHandler.dataSet.getElectronsFromRawData()
            if min==-999999999:
                timeFilter=(None,None)
            else:
                timeFilter=(self.dataHandler.dataSet.unitsToRawData(min,"T"),self.dataHandler.dataSet.unitsToRawData(max,"T"))
            if not timeFilter[0]==None and not timeFilter[1]==None:
                electrons = electrons[np.logical_and(electrons["time"] > timeFilter[0], electrons["time"] < timeFilter[1])]
            elif not timeFilter[0]==None:
                electrons = electrons[electrons["time"] > timeFilter[0]]
            elif not timeFilter[1]==None:
                electrons = electrons[electrons["time"] < timeFilter[1]]

            self.dataHandler.dataSet.setElectrons(electrons=electrons,spectrum="timeImage")
            self.updateView({"timeImage":np.copy(self.dataHandler.dataSet.timeImage)})


    def timeConfigChanged(self):
        with self.dataHandler:
            if not self.dataHandler.dataSet.rawData==None:
                self.dataHandler.dataSet.setTimeRange()
                self.dataHandler.dataSet.setTimeImageRange()
                electrons=self.dataHandler.dataSet.getElectronsFromRawData()
                self.dataHandler.dataSet.setElectrons(electrons=electrons,spectrum=["timeHistogram","timeImage"])
                self.dataHandler.dataTransfer(["timeHistogram","timeImage"])

            else:
                self.dataHandler.dataSet.initialize()
                self.dataHandler.sigUpdateRequest.emit(["all"])


    def updateView(self, data=None):
            if data==None:
                self.dataHandler.sigUpdateRequest.emit("all")
                return
            if "timeHistogram" in data:
                self.timeHistogram.updateData(data["timeHistogram"][0],data["timeHistogram"][1])
            if "energyHistogram" in data:
                self.energyHistogram.updateData(data["energyHistogram"][0],data["energyHistogram"][1])
            if "timeImage" in data:
                self.timeImage.updateData(data["timeImage"])
            if "energyImage" in data:
                self.energyImage.updateData(data["energyImage"])
            if "countrate" in data:
                self.countrate.updateData(data["countrate"][0],data["countrate"][1])
            if "keithley" in data:
                self.keithley.updateData(data["keithley"][0],data["keithley"][1])
            if "liveView" in data:
                if self.liveView!=None:

                    self.liveView.updateData(data["liveView"][0])
                    self.liveView.countrate.setValue(data["liveView"][1])
                    self.liveView.selection.setValue(data["liveView"][2])

    def setDLDParameter(self,factors,offsets,pxLimits): #set from dld
        self.configWidget.setDLLParams(factors=factors,offsets=offsets,pxLimits=pxLimits)

    def createConversion(self,dialog=False,recommended=False):
        conversion=EnergyConversion.ConversionItem(self.dataHandler.dataSet,self.configWidget)
        with self.dataHandler:
            if not self.dataHandler.dataSet.rawData==None: conversion.control.state.getEventData()._data=self.dataHandler.dataSet.getElectronsFromRawData()
        if dialog:
            newconversion=conversion.startConversionDialog()
        else:
            self.throwMessage.emit("Create ConversionSplines",2)
            newconversion=conversion.createStandardConversion(recommended=recommended)
            self.throwMessage.emit("--> Finished",4)
        if newconversion==None: return
        self.configWidget.setEnergyParams(newconversion.factors,newconversion.offsets)
        with self.dataHandler:
            self.dataHandler.dataSet.conversion=conversion
            self.dataHandler.dataSet.energyHistogram=np.sum(np.sum(newconversion.getDataContent(),0),0)
            self.dataHandler.dataSet.energyImage=np.sum(newconversion.getDataContent(),2)
            self.dataHandler.dataSet.setEnergyRange()

        self.energyImage.setExtent()
        self.dataHandler.sigUpdateRequest.emit(["energyHistogram","energyImage"])



    def startConversionDialog(self):
        self.createConversion(dialog=True)

    def createStandardConversion(self):
        self.createConversion()


    def clearSpectra(self,rawData=True):
        QtCore.QMetaObject.invokeMethod(self.dataHandler,"clearSpectra",QtCore.Qt.QueuedConnection,QtCore.Q_ARG(bool,True))
        # with self.dataHandler:
        #
        #     self.dataHandler.dataSet.clearSpectra()
        #     self.dataHandler.electrons=np.empty(0, [("x", 'i2'), ("y", 'i2'), ("time", 'i4')])
        # if rawData:
        #     self.dataHandler.closeRawData()
        # self.dataHandler.sigUpdateRequest.emit(["all"])

    def saveMeasurement(self,confirm=True,autoOverride=False):
        path=self.config["File Configuration","Folder"]
        if path=="Default": path=fileaccess.createDefaultPath(self.config["File Configuration","Folder","Beamtime"],self.config["File Configuration","Folder","Groupname"])
        else: path=self.config["File Configuration","Folder","Custom Folder"]
        if not fileaccess.checkIfPathExist(path):
            self.throwMessage.emit("--> Could not create the desired Path",0)
            self.throwMessage.emit("--> Measurement was not Saved",2)
            return False
        filename=self.config["File Configuration","Filename"]
        if self.themisApp!=None:
            filename=filename.replace("%n",("%03d"% self.themisApp.parent.joblist.measurementNumber.value()))
            self.themisApp.parent.joblist.measurementNumber.setValue(self.themisApp.parent.joblist.measurementNumber.value()+1)
        file=path+"/"+filename+".lv"
        if not autoOverride:
            if fileaccess.checkIfFileExists(file):
                file=fileaccess.fileOverwriteDialog(file,path)
                if file==None:
                    self.throwMessage.emit("--> Measurement was not Saved",2)
                    return False
        self.throwMessage.emit("Save Measurement as: "+file,2)
        file=file.replace("/","\\")
        with self.dataHandler:
            if not self.dataHandler.dataSet.rawData==None and self.dataHandler.dataSet.rawData.filename.replace("/","\\")==file.replace("/","\\"):
                file=file+"_temporay_while_edited"
            h5file = fileaccess.openFile(file, mode = "w", title = "Measurement")

            ##! Adjust and Save Config
            config=self.config.saveState()
            config["children"]["File Configuration"]["children"]["Folder"]["children"]["Custom Folder"]["value"]=path
            config["children"]["File Configuration"]["children"]["Folder"]["value"]="Custom"
            config["children"]["File Configuration"]["children"]["Filename"]["value"]=filename
            if config["children"]["Measurement Info"]["children"]["End of Acquisition"]["value"]=="not yet finished":
                config["children"]["Measurement Info"]["children"]["End of Acquisition"]["value"]=datetime.datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
            h5file.root._v_attrs.config=str(config)
            self.dataHandler.dataSet.saveDataSet(h5file)
            h5file.flush()
            if "_temporay_while_edited" in file:
                self.dataHandler.dataSet.rawData.close()
                _cwd=os.getcwd()
                os.chdir(path)
                name=file.split("\\")[-1]
                os.remove(file[0:-22])
                h5file.close()
                os.rename(name,name[0:-22])
                self.dataHandler.dataSet.rawData=fileaccess.openFile(file[0:-22], mode = "a")
                self.dataHandler.dataSet.events=self.dataHandler.dataSet.rawData.getNode("/rawData/", "events")
            else:
                h5file.close()

            if self.config["File Configuration","Copy to Grouphome"]:
                grouphome=path.replace("C:/","Z:/")
                if grouphome==path: return
                try:
                    fileaccess.checkIfPathExist(grouphome,create=True)
                    shutil.copy(file,grouphome)
                except(WindowsError):
                    self.throwMessage.emit("Error: Could not connect to Grouphome",2)
            if confirm:
                msgBox=QtGui.QMessageBox(self.viewer)
                msgBox.setWindowTitle("Measurement Saved")
                msgBox.setText("Measurement has been saved to:")
                msgBox.setInformativeText(file)
                msgBox.exec_()

    @staticmethod
    def loadMeasurement(file,mode="r"):
        measurement=Measurement()
        measurement.load(file,mode=mode)
        return(measurement)

    def load(self,file,mode="r"):
        self.viewer.setWindowTitle("Data Viewer - "+ file)

        if not fileaccess.checkIfFileExists(file):
            self.throwMessage.emit("Load Error: File "+file+" not found",0)
            return
        h5file = fileaccess.openFile(file, mode = mode)
        h5file =self.configWidget.restoreState(h5file,file=file)

        with self.dataHandler:
            self.dataHandler.dataSet.config=self.configWidget.toDict()
            self.dataHandler.dataSet.loadDataSet(h5file)
        self.timeImage.setExtent()
        self.energyImage.setExtent()
        self.dataHandler.sigUpdateRequest.emit(["all"])



    def show(self):
        self.viewer.show()


def excepthook(type, value, tb):
    traceback.print_tb(tb)
    print(value)
    box = QtGui.QMessageBox(QtGui.QMessageBox.Critical, "Error", str(value))
    box.setDetailedText("".join(traceback.format_tb(tb)))
    box.exec_()

if __name__ == '__main__':
    from Daniel import SaveSettings
    import os
    import traceback
    import warnings
    import sip
    sip.setdestroyonexit(False)

    app = QtGui.QApplication(sys.argv)
    os.chdir(os.path.split(sys.argv[0])[0]) #needed for opening from different locations

    app_icon = QtGui.QIcon("labControl.ico")
    app.setWindowIcon(app_icon)
    sys.excepthook = excepthook
    warnings.simplefilter('ignore')


    if len(sys.argv)>1:
        with SaveSettings.rememberSettings("LabControl.ini") as settings:
            measurementItem=Measurement.loadMeasurement(sys.argv[1])
            settings.restoreObject(measurementItem.viewer.area,group="Measurement")
            settings.restoreObject(measurementItem.viewer,group="Measurement")
            measurementItem.show()
            app.exec_()



    else:

        with SaveSettings.rememberSettings("LabControl.ini") as settings:
            measurementItem=Measurement.loadMeasurement(r"X:\TOF-data\FU_2014\NanoDiamonds\2014-11-28\DriftModeDifferenceSpectrum207\006_Nd10mg_dmm__piOpen_thOpen.lv")
            #measurementItem.load(r"X:\programs\LabControl_3.0\test.lv")
            settings.restoreObject(measurementItem.viewer.area,group="Measurement")
            settings.restoreObject(measurementItem.viewer,group="Measurement")
            measurementItem.show()
            app.exec_()

    measurementItem.finalize()
    sys.exit(0)




