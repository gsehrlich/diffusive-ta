# -*- coding: utf-8 -*-
"""
Created on Mon Jul 21 20:44:01 2014

@author: tolken
"""
#from Daniel.Scripts.startUp import *
import numpy as np
import math
import bisect
from guiqwt.plot import ImageDialog
from guiqwt.builder import make
import guidata
import collections
import PyQt4
from PyQt4 import QtCore,QtGui
import os
from Daniel.Scripts.ProgressBar import ProgressBar
import tables
import scipy
from scipy import interpolate
import matplotlib as mpl
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from Daniel.configurationWidget import configurationWidget
import traceback
import gc
import datetime
mpl.rcParams['axes.formatter.useoffset']=False
mpl.pyplot.ioff()
from IPython.html.widgets import interact
from IPython.display import display
#from Daniel.Scripts.startUp import *



def gaussfit(x,y):
    if not isinstance(x,np.ndarray):
        x=np.array(x)
        y=np.array(y)
    from guiqwt.widgets.fit import FitParam, guifit
    def fit(x, params):
        A, mu, FWHM,b = params
        return A*np.exp(-4*math.log(2)*np.power((x-mu),2)/math.pow(FWHM,2))+b
        
    
    A = FitParam("Amplitude", y.max(), 0., y.max())
    mu = FitParam("mu", x[len(x)/2], x[0], x[-1])
    FWHM = FitParam("FWHM", (x.max()-x.min())/4, 0., x.max()-x.min())
    b = FitParam("Offset", 0, 0., y.max())
    params = [A, mu, FWHM,b]
    values = guifit(x, y, fit, params, xlabel="Time (s)", ylabel="Power (a.u.)",auto_fit=True)    
    return(values)
    #print([param.value for param in params])
    
def sort(x,y):
    xs=[]
    ys=[]
    for i in range(len(x)):
        j=bisect.bisect_left(xs,x[i])
        xs.insert(j,x[i])
        ys.insert(j,y[i])
    return (np.array(xs),np.array(ys))


def runningMean(x, N):
    if N==1:
        return x
    #return np.convolve(x, np.ones((N,))/N,)[(N-1):]    
    return np.append(np.convolve(x, np.ones((N,))/N,mode="valid"),x[-(N-1):])

def movingAverage (values, window):
    weights = np.repeat(1.0, window)/window
    sma = np.convolve(values, weights, 'same')
    return sma

def movingAverage2(array,order=5):
    if order==0 or order==1:
        return array
    newArray=np.empty(len(array))
    newArray[0]=array[0]
    newArray[-1]=array[-1]
    for i in range(1,len(array)-1,1):
        newArray[i]=np.average(array[max(0,i-order):min(array.shape[0],i+order)])
    return newArray

def averageArray(ndarray,n,dim=0, operation='mean'):
    new_shape=list(ndarray.shape)    
    rest=new_shape[dim]%n    
    if rest!=0:
        cond=np.empty(new_shape[dim])   
        cond[:new_shape[dim]-rest]=True
        cond[new_shape[dim]-rest:]=False
        ndarray=np.compress(cond,ndarray,axis=dim)        
      
    new_shape=list(ndarray.shape)
    new_shape[dim]=new_shape[dim]//n
    
    
    if not operation.lower() in ['sum', 'mean', 'average', 'avg']:
        raise ValueError("Operation not supported.")
    if ndarray.ndim != len(new_shape):
        raise ValueError("Shape mismatch: {} -> {}".format(ndarray.shape,
                                                           new_shape))
    compression_pairs = [(d, c//d) for d,c in zip(new_shape,
                                                  ndarray.shape)]
    flattened = [l for p in compression_pairs for l in p]
    ndarray = ndarray.reshape(flattened)
    for i in range(len(new_shape)):
        if operation.lower() == "sum":
            ndarray = ndarray.sum(-1*(i+1))
        elif operation.lower() in ["mean", "average", "avg"]:
            ndarray = ndarray.mean(-1*(i+1))
    return ndarray

#def averageArray(a,n=2,dim=0):
#    def resize_with_average(a,shape):    
#        sh = shape[0],a.shape[0]//shape[0],shape[1],a.shape[1]//shape[1]
#        return a.reshape(sh).mean(-1).mean(1)
#
#    newShape=list(a.shape)
#    rest=newShape[dim]%n
#    if rest!=0:        
#        newShape[dim]=newShape[dim]-(newShape[dim]%n)
#        a=np.resize(a,newShape)
#    shape=list(a.shape)
#    shape[dim]=shape[dim]//n
#    return resize_with_average(a,shape)
 
def plotImage(x,y,z,wintitle="Contour Plot",options={"lock_aspect_ratio":False,"yreverse":False}):
    options.update(dict(show_xsection=True, show_ysection=True))
    """Test"""
    # -- Create QApplication    
    _app = guidata.qapplication()
    # --
    win = ImageDialog(edit=True, toolbar=True, wintitle=wintitle,
                      options=options)
    win.resize(1500, 1000)
    item = make.xyimage(x, y, z,interpolation="linear")    
    plot = win.get_plot()
    plot.add_item(item)        
    win.plot_widget.xcsw_splitter.setSizes([400,600])
    win.show()
    return win
    #win.exec_()

def fitFunction(self,func,x,y,initalGuess,method=None):
    
    def ChiSquare(x,params):
        yFit=func(x,params)        
        return (np.sum(np.power(yFit-y,2)))
    

def calcInterpolated(x1,y1,x2,y2,operator="-",kind='linear'):
    xMin=x1[0] if x1[0]>x2[0] else x2[0]
    xMax=x1[-1] if x1[-1]<x2[-1] else x2[-1]
    f1=scipy.interpolate.interp1d(x1, y1,kind=kind)
    f2=scipy.interpolate.interp1d(x2, y2,kind=kind)
    newX=np.linspace(xMin,xMax,len(x1))
    if operator=="-":
        newY=f1(newX)-f2(newX)
    if operator=="+":
        newY=f1(newX)+f2(newX)
    if operator=="*":
        newY=f1(newX)*f2(newX)
    if operator=="/":
        newY=f1(newX)/f2(newX)
    return (newX,newY)
    
def subtractInterpolated(x1,y1,x2,y2):
    xMin=x1[0] if x1[0]>x2[0] else x2[0]
    xMax=x1[-1] if x1[-1]<x2[-1] else x2[-1]
    f1=scipy.interpolate.interp1d(x1, y1)
    f2=scipy.interpolate.interp1d(x2, y2)
    newX=np.linspace(xMin,xMax,len(x1))
    newY=f1(newX)-f2(newX)
    return (newX,newY)

def IndexOf(array,value,method="nearest"):
    if method=="nearest":
       return (np.abs(array-value)).argmin()
    if method=="higher":
        return np.argmax(array>=value)
    if method=="lower":
        return np.argmin(array<=value)-1

def addInterpolated(x1,y1,x2,y2):
    xMin=x1[0] if x1[0]>x2[0] else x2[0]
    xMax=x1[-1] if x1[-1]<x2[-1] else x2[-1]
    f1=interpolate.interp1d(x1, y1)
    f2=interpolate.interp1d(x2, y2)
    newX=np.linspace(xMin,xMax,len(x1))
    newY=f1(newX)+f2(newX)
    return (newX,newY)
    
def meanInterpolated(x1,y1,x2,y2,w1=1,w2=1):
    f1=interpolate.interp1d(x1, y1,bounds_error=False)
    f2=interpolate.interp1d(x2, y2,bounds_error=False)
    newX=np.unique(np.append(x1,x2))
    newY=(w1*f1(newX)+w2*f2(newX))/float(w1+w2)
    nans=np.where(np.isnan(newY))#newY.where(np.NaN)
    for i in nans[0]:        
        if newX[i] in x1:
            newY[i]=y1[IndexOf(x1,newX[i])]
        else:
            newY[i]=y2[IndexOf(x2,newX[i])]
    return (newX,newY)

def checkFileHasGroup(file, name):
        for group in file.walkNodes():
            if group._v_name == name:
                return True
        return False
  
def checkIfPathExist(dir,create=True):
    if not os.path.exists(dir):
        if create:
            print("create Path: ", dir)         
            os.makedirs(dir)
            return True
        else: return False
    else: return True

def combinePlotData(x1,y1,plotData1,x2,y2,plotData2,method="mean",weight=[1,1],fill=0):
    newX=np.unique(np.append(x1,x2))
    newY=np.unique(np.append(y1,y2))
    newPlotData=np.empty((len(newX),len(newY)))
    for i in range(len(newX)):
        x1_index=np.where(x1==newX[i])
        x2_index=np.where(x2==newX[i])
        for j in range(len(newY)):
            val=0
            x1_index=np.where(x1,newX[i])
            if newX[x] in x1 and newY[y] in y1:
                val+=plotData1[IndexOf(x1,newX[x]),y]*weight[0]
                if newX[x] in x2 and newY[y] in y2:
                    val+=plotData2[x,y]*weight[1]
                else:
                    val+=plotData1[x,y]*weight[1]
            elif newX[x] in x2 and newY[y] in y2:
                val+=plotData2[x,y]*(weight[0]+weight[1])
            else: val=fill
            newPlotData[x,y]=val
    if method=="mean":
        newPlotData=newPlotData/(weight[0]+weight[1])
    return(newX,newY,newPlotData)




def savetxt(fname,x,y,newline="\r\n",**kwgs):
    """
    Saves an x and y array to a textfile
    fname= Filename
    For information on kwgs see numpy.savetxt
    """
    checkIfPathExist(os.path.split(fname)[0])

    #txtData=np.empty((len(x),2))
    #txtData[:,0]=x
    #txtData[:,1]=y

    #np.savetxt(fname,txtData,**kwgs)
    np.savetxt(fname,np.c_[x,y],newline=newline,**kwgs)
    
    
def copyFilesToLocal(path,drive="C",overwriteExsiting=False):   
    newPath=drive+path[1:]
    if newPath==path: return
    checkIfPathExist(newPath,create=True)
    files=[path+"/"+file for file in os.listdir(path) if ".lv" in file]
    print("Copy Files to Grouphome")
    for m in files:
        m_new=drive+m[1:]
        if not os.path.exists(m_new) or overwriteExsiting:
            print("     ",m_new)
            shutil.copy(m,m_new)
    print("Copying finsished!")
    return newPath

def selectFiles(path,filters=None,files=None):    
    selectedFiles=[path+"/"+file for file in os.listdir(path) if ".lv" in file]
    if files!=None:  
        if not isinstance(files,(list,tuple)): files=[files]
        selectedFiles=[selectedFiles[i] for i in files]
    if filters!=None:
        if not isinstance(filters,(list,tuple)): filters=[filters]
        for f in filters:
            selectedFiles=[selectedFiles[i] for i in range(len(selectedFiles)) if f in selectedFiles[i]]
    selectedFiles=[file.replace("/","\\") for file in selectedFiles]
    return selectedFiles


def getFilteredCountrate(file=None,Measurement=None,Emin=None,Emax=None):
    if file!=None:   
        data=Daniel.fileaccess.fileaccess.loadMeasurementItem(file,mode="r")
    data.createConversion()
    electrons=data.fileaccess.getElectronsFromRawData()    
    countrate=data.fileaccess.getCountrateFromRawData()
    data.fileaccess.closeRawData()
    if Emin==None:
        Emin=0   
    if Emax==None:
        Emax=len(data.energyHistogram.energyRange-1)
    e1=IndexOf(data.energyHistogram.energyRange,Emin,method="higher")
    e2=IndexOf(data.energyHistogram.energyRange,Emax,method="lower")
    n=0
    for i in range(countrate.shape[0]):
        c=countrate[i]["events"]        
        data.dataSet.setElectrons(electrons[n:n+c])
        countrate[i]["events"]=np.sum(data.dataSet.energyHistogram[e1:e2])
        n+=c
    return countrate
    #plt.plot(countrate["eventTime"],countrate["events"])
        
        
        


class SlimMeasurement():
    def __init__(self,path=None,config=None,spectrum=None):
        self.spectrum=spectrum
        self.delayStage=config["Measurement Info","Delaystage"]
        self.startTime=config["Measurement Info","Begin of Acquisition"]
        self.keithley=None
        self.path=path
        self.filename=config["File Configuration","Filename"]
    def getConfig():
        config=configurationWidget()
        file=self.path+"/"+self.filename
        h5file = tables.openFile(file, mode = "r")
        config.restoreState(h5file.root._v_attrs.config) 
        h5file.close()
        return(config.p)
                
class SlimData(QtCore.QObject):
    dataUpdated=QtCore.pyqtSignal()
    def __init__(self):
        QtCore.QObject.__init__(self)   
        self.path=None
        self.filters=None
        self.useSpectrum=None
        self.autoUpdate=None
        self.files=None
        self.useLocalDrive=None
        self.sort=None
        self.measurements={}
    def copy(self):
        newData=SlimMeasurement()
        newData.path=self.path
        newData.filters=self.filters
        newData.useSpectrum=self.useSpectrum
        newData.autoUpdate=False
        newData.files=self.files
        newData.useLocalDrive=self.useLocalDrive=None
        newData.sort=self.sort=None
        newData.measurements=self.measurements
        return(newData)
    
    def setSettings(self,path=None,files=None,filters=None,useSpectrum="Energy",sort=False,autoUpdate=False,useLocalDrive=False):
        if self.useSpectrum!=useSpectrum or self.filters!=filters or self.path!=path or self.autoUpdate!=autoUpdate or self.useLocalDrive!=useLocalDrive or self.sort!=sort or self.files!=files:
            #del self.measurements            
            self.measurements={}                
            gc.collect()            
            self.xRange=None            
            self.path=path
            self.filters=filters
            self.useSpectrum=useSpectrum
            self.autoUpdate=autoUpdate
            self.files=files
            self.sort=sort
            self.useLocalDrive=useLocalDrive
            if autoUpdate==True:
                self.folderWatcher=QtCore.QFileSystemWatcher()
                self.folderWatcher.directoryChanged.connect(self.updateData)
                self.folderWatcher.addPath(self.path)
            else:
                self.folderWatcher=None
        self.loadData(self.path,files=self.files)


    def loadData(self,path=None,files=None): 
        if self.useLocalDrive!=None and self.useLocalDrive!=False:
            if self.useLocalDrive==True: self.useLocalDrive="C"
            path=copyFilesToLocal(path,self.useLocalDrive)
        selectedFiles=[path+"/"+file for file in os.listdir(path) if ".lv" in file]
        if files!=None:  
            if not isinstance(files,(list,tuple)): files=[files]
            selectedFiles=[selectedFiles[i] for i in files]
        if self.filters!=None:
            if not isinstance(self.filters,(list,tuple)): self.filters=[self.filters]
            for f in self.filters:
                selectedFiles=[selectedFiles[i] for i in range(len(selectedFiles)) if f in selectedFiles[i]]
        updated=False 
        progress = ProgressBar(len(selectedFiles))
        i=0
        print("load Data from: "+path)
        progress.run(i)
        config=configurationWidget()   
        for file in selectedFiles:
            if not file in list(self.measurements.keys()):
                h5file = tables.openFile(file, mode = "r")               
                #print '\r', "load Data: "+file.split("\\")[-1], 
                i+=1
                progress.run(i)
                h5file =config.restoreState(h5file,file=file)
                m=SlimMeasurement(config=config.p,path=path)   
                if self.useSpectrum=="TOF":                
                    m.spectrum=h5file.getNode("/spectra", "timeHistogram").read()
                    if self.xRange==None:
                        self.xRange=np.arange(config.p["Spectra","Time Histogram","Time min"],config.p["Spectra","Time Histogram","Time max"],config.p["Spectra","Time Histogram","Time resolution"])
                elif self.useSpectrum=="Energy":
                    m.spectrum=h5file.getNode("/spectra", "energyHistogram").read()            
                    if self.xRange==None:            
                        setting=config.p.param(("DLLParams"))
                        self.xRange=np.arange(-setting["E offset"],m.spectrum.shape[0]*setting["E factor"]-setting["E offset"]-setting["E factor"]/4.,setting["E factor"])
                if checkFileHasGroup(h5file,"keithley"):
                    m.keithley=h5file.getNode("/spectra", "keithley").read()
               

                self.measurements[file]=m
                h5file.close()
                updated=True        
        progress.run(len(selectedFiles))
        if self.sort!=None and self.sort!=False:
            self.sortMeasurements(self.sort)
        if updated: self.dataUpdated.emit() 
        print("") 
        
    def XYZData(self,key="Delay"):
        i=0
        dupli=0
        count=len(self.measurements)                         
        plotData=np.empty((len(self.xRange),count))  
        x=np.empty(count)
        plotData[:,0]=list(self.measurements.values())[0].spectrum
        if key=="Delay":
            def xValue(j):
                return list(self.measurements.values())[j].delayStage
        elif key=="Keithley":
            def xValue(j):
                return np.average(list(self.measurements.values())[j].keithley["events"])
        elif key=="creationTime":
            startTime=datetime.datetime.strptime(list(self.measurements.values())[0].startTime, '%Y-%m-%d, %H:%M:%S')
            def xValue(j):
                creationTime=datetime.datetime.strptime(list(self.measurements.values())[j].startTime, '%Y-%m-%d, %H:%M:%S')
                return((creationTime-startTime).total_seconds()/60.)
        elif key=="timestamp":
            x=list(range(count))
            def xValue(j):
                return(datetime.datetime.strptime(list(self.measurements.values())[j].startTime, '%Y-%m-%d, %H:%M:%S'))
                #return(datetime.datetime.fromtimestamp(os.path.getctime(list(self.measurements.keys())[j])))
        else:
            def xValue(j):
                return(j)

        x[0]=xValue(0)
        while i<count:
            xVal=xValue(i)
            if xVal==x[i-1-dupli]:
                plotData[:,i-dupli]=(plotData[:,i-dupli]+list(self.measurements.values())[i].spectrum)/2.
                dupli=dupli+1
            else:
                plotData[:,i-dupli]=list(self.measurements.values())[i].spectrum
            x[i-dupli]=xVal
            i+=1        
        if dupli>0:
            return(x[:-dupli],self.xRange,plotData[:,:-dupli])
        else :
            return x,self.xRange,plotData
    
    def showData(self,xlim=None,ylim=None,clim=None,colormap='log'):#       
        x,y,plotData=self.XYZData()
        
   
        if colormap=='log':
            lvls=np.logspace(0,math.log(np.max(plotData),10),100)
            norm=matplotlib.colors.LogNorm()
        else: 
            lvls=None
            norm=None
        CS = plt.contourf(x, self.xRange, plotData, cmap=plt.cm.spectral,
                  levels = lvls,norm=norm)
        cbar=plt.colorbar(format='%g')
        #plt.show()
            
    def updateData(self):
        self.loadData(self.path)
        
            
    def sortMeasurements(self,key="Filename",reverse=False):
        if key=="Filename":
            def getter(m):
                return m[1].filename            
        if key=="DelayStage":
            def getter(m):                
                return m[1].delayStage
        if key=="Keithley":
            def getter(m):
                return(np.sum(m[1].keithley["events"]))
        if key=="creationTime":
            def getter(m):
                return(datetime.datetime.strptime(m[1].startTime, '%Y-%m-%d, %H:%M:%S'))
                #return(datetime.datetime.fromtimestamp(os.path.getctime(m[0])))
        self.measurements=collections.OrderedDict(sorted(list(self.measurements.items()), key=getter,reverse=reverse))

    def __getitem__(self,index):
        return list(self.measurements.values())[index]


        
        
class Logfile(QtGui.QTextEdit):
    def __init__(self):
        QtGui.QTextEdit.__init__(self)
        self.setGeometry(200,50,600,800)
        sys.stdout = self
        sys.excepthook=self.excepthook
        self.error=False
    def excepthook(self,type, value, tb):
        #print value
        #print tb
        traceback.print_tb(tb)        
        if type is Exception:
            message = value.args[0]
            detailed = value.args[1]
        else:
            message = "".join(traceback.format_exception_only(type, value) + [" " * 100])
            detailed = "".join(traceback.format_tb(tb))
        self.error=True
        file = open("ErrorDiscription.txt", "w")
        file.write(detailed+"\n"+message)
        file.close()
        self.write(detailed+"\n"+message)
        
    def flush(self):
        pass
        
    def write(self,msg):
        if "\r" in msg: self.undo()
        self.append(msg)
        #self.scrollToBottom()
        self.repaint()
 

class MatplotlibWidget(FigureCanvas):
    def __init__(self,toolbar=False):
        
        #self.name=name
        #plt.figure(name)
        #self.fig = plt.gcf()    
        self.fig=plt.figure(tight_layout=False)
        #plt.figure(self.fig)
        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self,QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)
        self.setAttribute(QtCore.Qt.WA_PaintOnScreen)
        self.setMouseTracking(True)
        self.fig.patch.set_facecolor("w")
        if toolbar==True:
            from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
            self.mpl_toolbar = NavigationToolbar(self,self)
            #self.layout().addWidget(self.mpl_toolbar)
        #plt.close()
    def activate(self):
        plt.figure(self.fig.number)
        

class SliderPlot():
    def __init__(self):
        self.plots=[]
        self.i=1
        self.plots.append(plt.figure())
    def nextPlot(self):
        plt.close(self.plots[self.i-1])
        self.i+=1
        self.plots.append(plt.figure())
    def showFigure(self,i=0):
        display(self.plots[i-1])
    def close(self):
        plt.close(self.plots[self.i-1])
    def show(self):
        plt.close(self.plots[self.i-1])
        interact(self.showFigure,i=[1,self.i,1])

## Cache Decorator for functions
def memoize(f):
  class memodict(dict):
      __slots__ = ()
      def __missing__(self, key):
          self[key] = ret = f(key)
          return ret
  return memodict().__getitem__

class PlotArray():
    def __init__(self,count,cols=3,width=17,height=None):
        plt.ioff()
        self.cols=min(count,cols)
        self.rows=max(math.ceil(count/float(self.cols)),1)        
        self.count=count
        if height==None:
            height=width/self.cols*0.9*self.rows
        mpl.rcParams['figure.figsize'] = (width, height)
        self.i=2
        plt.subplot(self.rows,self.cols,1)
        
    def nextPlot(self):
        if self.i<=self.count:        
            plt.subplot(self.rows,self.cols,self.i)
            self.i+=1
    def finalize(self):
        plt.tight_layout()
        
if __name__=="__main__":
    #from Daniel.Scripts.startUp import *    
    #initalize()
    a=np.linspace(1,15,15)
    a=a.reshape((3,5))
    x=np.linspace(1,5,5)
    print(a)
    
#    ndarray=a
#    dim=1
#    n=2
#    
#    new_shape=list(ndarray.shape)    
#    rest=new_shape[dim]%n    
#    if rest!=0:
#        cond=np.empty(new_shape[dim])   
#        cond[:new_shape[dim]-rest]=True
#        cond[new_shape[dim]-rest:]=False
#        ndarray=np.compress(cond,ndarray,axis=dim)
#        
#        print ndarray
    
    
    print("---------------")
    b=averageArray(a,2,dim=1,operation="sum")
    print("---------------")
    print(b)
    print("---------------")
    print(x)
    print(averageArray(x,2))
    
    #startApplication()
    
