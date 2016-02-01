import numpy as np
import math
import fileaccess
from PyQt4.QtCore import pyqtSlot

from PyQt4.QtCore import pyqtSignal, QObject

class DynamicCountrate(object):
    def __init__(self, intialSize=5000,array=None):
        if not array==None:
            self._data=array
            self._size=array.shape[0]
        else:
            self._data = np.empty(intialSize, [("eventTime", 'float'), ("events", 'i4')])
            self._size = 0

    def getData(self):
        return self._data[:self._size]

    def clear(self):
        self._size=0

    def append(self, time, value):
        if not isinstance(time,np.ndarray):
            if not isinstance(time,list):
                time=[time]
                value=[value]
            time=np.array(time)
            value=np.array(value)
        n=time.shape[0]
        if self._data.shape[0] < self._size+n:
            self._data = np.resize(self._data, (int(len(self._data)*2)))#,int(len(self._data)*2)))
        self._data["eventTime"][self._size:self._size+n] = time
        self._data["events"][self._size:self._size+n] = value
        self._size += n

    def appendMulti(self,countrate):
        newSize=self._size+countrate.shape[0]
        if newSize>=self._data.shape[0]:
            self._data=np.resize(self._data,int(newSize*1.2))        
        self._data[self._size:newSize]=countrate        
        self._size=newSize

class DynamicKeithley(DynamicCountrate):
    def __init__(self, intialSize=5000,array=None):
        if not array==None:
            self._data=array
            self._size=array.shape[0]
        else:
            self._data = np.empty(intialSize, [("eventTime", 'float'), ("events", 'float')])
            self._size = 0

class Dataset(QObject):
    def __init__(self,parent,config):
        QObject.__init__(self,parent)
        self.conversion=None
        self.config=config
        self.zeroEnergy=0
        self.initialize()
        self.rawData=None
        self.events=None


    def rawDataToUnits(self,value,axis="X"):
            return (value*self.config["DLLParams/"+axis+" factor"]-self.config["DLLParams/"+axis+" offset"])
    def unitsToRawData(self,value,axis):
            return (value+self.config["DLLParams/"+axis+" offset"])/self.config["DLLParams/"+axis+" factor"]


    def setTimeRange(self):
        self.timeRange=np.arange(self.config["Spectra/Time Histogram/Time min"],self.config["Spectra/Time Histogram/Time max"],self.config["Spectra/Time Histogram/Time resolution"])
        self.tbins=self.timeRange.shape[0]
        self.tedges=(self.unitsToRawData(self.config["Spectra/Time Histogram/Time min"],"T"),self.unitsToRawData(self.config["Spectra/Time Histogram/Time max"],"T"))

    @pyqtSlot(float)
    def setEnergyRange(self,zeroEnergy=None):
        if zeroEnergy!=None:
            self.zeroEnergy=zeroEnergy
        self.energyRange=np.arange(-self.config["DLLParams/E offset"],self.energyHistogram.shape[0]*self.config["DLLParams/E factor"]-self.config["DLLParams/E offset"]
                                   -self.config["DLLParams/E factor"]/4.,self.config["DLLParams/E factor"])-self.zeroEnergy
    def setTimeImageRange(self):
        self.tXYbins=[self.config["Spectra/Time Image/Xbins"],self.config["Spectra/Time Image/Ybins"]]
        self.tXYedges=[[self.unitsToRawData(self.config["DLLParams/X Min"],"X"),self.unitsToRawData(self.config["DLLParams/X Max"],"X")],
                [self.unitsToRawData(self.config["DLLParams/Y Min"],"Y"),self.unitsToRawData(self.config["DLLParams/Y Max"],"Y")]]



    def _del(self):
        pass

    def setElectrons(self,electrons=None,spectrum=["all"],countrate=None,keithley=None):
        if not electrons==None:
            electrons=self.rotateElectrons(electrons)
            if "timeHistogram" in spectrum or  "all" in spectrum:
                #self.setTimeRange()
                self.timeHistogram=np.histogram(electrons["time"],bins=self.tbins,range=self.tedges)[0]
            if "timeImage" in spectrum or "all" in spectrum:
                #self.setTimeImageRange()
                self.timeImage=np.histogram2d(electrons["x"],electrons["y"],bins=self.tXYbins,range=self.tXYedges)[0]
            if "energyHistogram" in spectrum or "all" in spectrum or "energyImage" in spectrum:
                if not self.conversion==None:
                    convArray=self.conversion.convertElectrons(electrons)
                    if "energyHistogram" in spectrum or "all" in spectrum:
                        self.energyHistogram=np.sum(np.sum(convArray,0),0)                        
                    if "energyImage" in spectrum or "all" in spectrum:
                        self.energyImage=np.sum(convArray,2)
        if countrate!=None:
            self.countrate=countrate
        if keithley!=None:
            self.keithley=keithley


    def initialize(self):
        self.countrate=DynamicCountrate()
        self.keithley=DynamicKeithley()

        self.setTimeRange()
        self.timeHistogram=np.zeros(len(self.timeRange))

        self.setTimeImageRange()
        self.timeImage=np.zeros((self.tXYbins[0],self.tXYbins[1]))

        self.mcp=np.zeros((4,4))

        if not self.conversion==None:
            self.energyHistogram.fill(0)
            self.energyImage.fill(0)
        else:
            self.energyHistogram=np.zeros(2)
            self.energyRange=[0,100]
            self.energyImage=np.zeros(4).reshape((2,2))

    def addElectrons(self,electrons):
        electrons=self.rotateElectrons(electrons)
        self.timeHistogram+=np.histogram(electrons["time"],bins=self.tbins,range=self.tedges)[0]
        self.mcp=np.histogram2d(electrons["x"],electrons["y"],bins=self.tXYbins,range=self.tXYedges)[0]
        self.timeImage+=self.mcp
        if not self.conversion==None:
            convArray=self.conversion.convertElectrons(electrons)
            self.energyHistogram+=np.sum(np.sum(convArray,0),0)
            self.energyImage+=np.sum(convArray,2)

    def rotateElectrons(self,electrons):
        if not self.config["Spectra/Rotate MCP"]==0:
            newElectrons=np.empty(electrons.shape[0], [("x", 'f4'), ("y", 'f4'), ("time", 'i4')])
            newElectrons["x"]=(electrons["x"]*self.config["DLLParams/X factor"]-self.config["DLLParams/X offset"])
            newElectrons["y"]=(electrons["y"]*self.config["DLLParams/Y factor"]-self.config["DLLParams/Y offset"])
            newElectrons["time"]=electrons["time"]
            rot=self.config["Spectra/Rotate MCP"]*np.pi/180
            buffer=newElectrons["x"].copy()
            newElectrons["x"]=(newElectrons["x"])*math.cos(rot)-(newElectrons["y"])*math.sin(rot)
            newElectrons["y"]=(buffer)*math.sin(rot)+(newElectrons["y"])*math.cos(rot)
            result=np.empty(electrons.shape[0], [("x", 'f4'), ("y", 'f4'), ("time", 'i4')])
            result["x"]=(newElectrons["x"]+self.config["DLLParams/X offset"])/self.config["DLLParams/X factor"]
            result["y"]=(newElectrons["y"]+self.config["DLLParams/Y offset"])/self.config["DLLParams/Y factor"]
            result["time"]=electrons["time"]
            return(result)
        else: return electrons


    def clearSpectra(self,ignoreCountrate=False):
        self.timeImage.fill(0)
        self.timeHistogram.fill(0)
        if not ignoreCountrate:
            self.countrate.clear()
            self.keithley.clear()
        if not self.energyHistogram==None: self.energyHistogram.fill(0)
        if not self.energyImage==None: self.energyImage.fill(0)

    def dumpRawData(self,electrons):
        if self.rawData==None:
            self.rawData = fileaccess.openFile("rawDataBuffer.h5", mode = "w", title = "Test file")
            self.rawData.createGroup("/", 'rawData', 'rawData')
            #expectedRows=5000
            self.events=self.rawData.createTable("/rawData/",'events', electrons,"")
        else:
            self.events.append(electrons)
        self.rawData.flush()

    def getElectronsFromRawData(self):
        if self.rawData==None:
            raise Exception("No File is opend")
        if self.events==None:
            self.events=self.rawData.getNode("/rawData/", "events")
        return(self.events.read())


    def saveDataSet(self,h5file):
        if self.config["File Configuration/Save spectra"]:
            spectra = h5file.createGroup("/", 'spectra', 'Spectra')

            #TimeHistogram
            timeHistogram=h5file.createArray(spectra, 'timeHistogram', self.timeHistogram,"")
            timeHistogram._v_attrs.binOffset=self.config["Spectra/Time Histogram/Time min"]
            timeHistogram._v_attrs.binFactor=self.config["Spectra/Time Histogram/Time resolution"]
            timeHistogram._v_attrs.binUnit="ns"

            #Time Image
            timeImage=h5file.createArray(spectra, 'timeImage', self.timeImage,"")

            #Energy Image
            if not self.conversion==None:
                energyImage=h5file.createArray(spectra, 'energyImage', self.energyImage,"")

            #Countrate
            countrate=h5file.createTable(spectra, 'countrate', self.countrate.getData())

            #Keithley
            if self.keithley.getData().shape[0]!=0:
                h5file.createTable(spectra, 'keithley', self.keithley.getData())


            #EnergyHistogram
            if not self.conversion==None:
                energyHistogram=h5file.createArray(spectra, 'energyHistogram', self.energyHistogram,"")
                energyHistogram._v_attrs.binOffset=self.config["DLLParams/E offset"]
                energyHistogram._v_attrs.binFactor=self.config["DLLParams/E factor"]
                energyHistogram._v_attrs.binUnit="eV"

        if self.config["File Configuration/Save raw data"] and self.events!=None:
            if self.rawData!=None:
                rawData = h5file.createGroup("/", 'rawData', 'raw Data')
                h5file.createTable("/rawData/","events",self.events.read())

    def loadDataSet(self,h5file):
        self.initialize()
        if self.config["File Configuration/Save spectra"]:
            if fileaccess.checkFileHasGroup(h5file,"timeHistogram"):
                self.timeHistogram=h5file.getNode("/spectra", "timeHistogram").read()
            if fileaccess.checkFileHasGroup(h5file,"timeImage"):
                self.timeImage=h5file.getNode("/spectra", "timeImage").read()
            if fileaccess.checkFileHasGroup(h5file,"energyHistogram"):
                self.energyHistogram=h5file.getNode("/spectra", "energyHistogram").read()
                self.setEnergyRange()
            if fileaccess.checkFileHasGroup(h5file,"energyImage"):
                self.energyImage=h5file.getNode("/spectra", "energyImage").read()
            if fileaccess.checkFileHasGroup(h5file,"countrate"):
                self.countrate=DynamicCountrate(array=h5file.getNode("/spectra", "countrate").read())
            if fileaccess.checkFileHasGroup(h5file,"keithley"):
                self.keithley=DynamicCountrate(array=h5file.getNode("/spectra", "keithley").read())

        if self.rawData!=None:
            self.rawData.close()
            self.events=None
        self.rawData=h5file

        if not self.config["File Configuration/Save spectra"]:
            self.setElectrons(self.getElectronsFromRawData())



if __name__=="__main__":
    from PyQt4 import QtGui
    app = QtGui.QApplication([])

