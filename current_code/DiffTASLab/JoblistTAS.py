from PyQt4 import QtCore, QtGui
import numpy as np
import ExpanderWidget
import WorkerThread
from time import sleep
import os

class Joblist(QtCore.QAbstractTableModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self.jobs=[]
        self.measure=False

    def rowCount(self, QModelIndex_parent=None, *args, **kwargs):
        return len(self.jobs)

    def addRow(self,filename,acquisitionTime,delaystage,piShutter=None,thShutter=None,path=None,rotationstage=None):
        #self.insertRow(self.rowCount())
        self.beginInsertRows(QtCore.QModelIndex(),self.rowCount(),self.rowCount())
        job={}
        job["filename"]=str(filename)
        if acquisitionTime=="00:00:00": acquisitionTime="Infinity"
        job["acquisitionTime"]=str(acquisitionTime)
        job["delaystage"]=delaystage
        job["piShutter"]=str(piShutter)
        job["thShutter"]=str(thShutter)
        job["path"]=path
        job["rotationstage"]=rotationstage
        self.jobs.append(job)
        self.endInsertRows()

    def columnCount(self, QModelIndex_parent=None, *args, **kwargs):
        return 6

    def data(self, QModelIndex, int_role=None):
        if int_role==QtCore.Qt.DisplayRole:
            n=QModelIndex.column()
            if n == 0:
                return self.jobs[QModelIndex.row()]["filename"]
            elif n== 1:
                time=self.jobs[QModelIndex.row()]["acquisitionTime"]
                return (self.jobs[QModelIndex.row()]["acquisitionTime"])
            elif n == 2:
                if self.jobs[QModelIndex.row()]["delaystage"]==None: return("Disabled")
                else: return str(self.jobs[QModelIndex.row()]["delaystage"])
            elif  n== 3:
                if self.jobs[QModelIndex.row()]["piShutter"]==None: return ("Disabled")
                else: return self.jobs[QModelIndex.row()]["piShutter"]
            elif  n== 4:
                if self.jobs[QModelIndex.row()]["thShutter"]==None: return ("Disabled")
                else: return self.jobs[QModelIndex.row()]["thShutter"]
            elif n == 5:
                if self.jobs[QModelIndex.row()]["rotationstage"]==None: return("Disabled")
                else: return str(self.jobs[QModelIndex.row()]["rotationstage"])
        elif int_role==QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignCenter
        else:
            return None

    def setData(self, QModelIndex, QVariant, int_role=None):
        if int_role==QtCore.Qt.EditRole:
            n=QModelIndex.column()
            if n == 0:
                self.jobs[QModelIndex.row()]["filename"]=str(QVariant)
            if n == 1:
                time=str(QVariant.toString("hh:mm:ss"))
                if time=="00:00:00": time="Infinity"
                self.jobs[QModelIndex.row()]["acquisitionTime"]=time
            if n == 2:
                try:
                    value=float(QVariant)
                    self.jobs[QModelIndex.row()]["delaystage"]=value
                except(ValueError):
                    self.jobs[QModelIndex.row()]["delaystage"]=None
            if n == 3:
                shutter=str(QVariant)
                if shutter=="Disabled": self.jobs[QModelIndex.row()]["piShutter"]=shutter
                elif shutter=="Open": self.jobs[QModelIndex.row()]["piShutter"]=shutter
                elif shutter=="Close": self.jobs[QModelIndex.row()]["piShutter"]=shutter
            if n == 4:
                shutter=str(QVariant)
                if shutter=="Disabled": self.jobs[QModelIndex.row()]["thShutter"]=shutter
                elif shutter=="Open": self.jobs[QModelIndex.row()]["thShutter"]=shutter
                elif shutter=="Close": self.jobs[QModelIndex.row()]["thShutter"]=shutter
            if n == 5:
                try:
                    value=float(QVariant)
                    self.jobs[QModelIndex.row()]["rotationstage"]=value
                except(ValueError):
                    self.jobs[QModelIndex.row()]["rotationstage"]=None
            #self.ValueWasChanged.emit()
        return (True)

    def headerData(self, p_int, Qt_Orientation, int_role=None):
        if int_role==QtCore.Qt.DisplayRole:
            if Qt_Orientation==QtCore.Qt.Horizontal:
                if p_int==0:
                    return("Filenname")
                elif p_int==1:
                    return("Acquisition Time\n (HH::MM:SS)")
                elif p_int==2:
                    return("Delaystage (mm)")
                elif p_int==3:
                    return("Picard Shuter")
                elif p_int==4:
                    return("Thorlabs Shutter")
                elif p_int==5:
                    return("Rotationstage (grad)")
            if Qt_Orientation==QtCore.Qt.Vertical:
                return (p_int+1)
        else:
            return None

    def flags(self, QModelIndex):
        if QModelIndex.row()==0 and self.measure:
            return (QtCore.Qt.ItemIsSelectable  | QtCore.Qt.ItemIsEnabled)
        else:
            return (QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled )

    def insertRows(self, p_int, p_int_1=1, QModelIndex_parent=None, *args, **kwargs):
        self.beginInsertRows(QtCore.QModelIndex(),p_int,p_int+p_int_1-1)
        for i in range(p_int_1):
            job={}
            self.jobs.insert(p_int+i,job)
        self.endInsertRows()
        return True

    def removeRows(self, p_int, p_int_1, QModelIndex_parent=None, *args, **kwargs):

        if (p_int==0 and self.measure):
            p_int+=1
            p_int_1-=1
        self.beginRemoveRows(QtCore.QModelIndex(), p_int, p_int+p_int_1-1);
        for i in range(p_int+p_int_1-1,p_int-1,-1):
            self.jobs.pop(i)
        self.endRemoveRows()
        return (True)
    def clear(self):
        if self.measure: i=1
        else: i=0
        self.removeRows(i,self.rowCount(),QtCore.QModelIndex())

    def takeJob(self,index=0):
        job=self.jobs[index]
        self.removeRow(index,QtCore.QModelIndex())
        return (job)

    def getJob(self,index=0):
        return self.jobs[index]

    def moveRows(self, sourceParent, sourceRow, count, destinationParent, destinationChild):
        self.beginMoveRows(sourceParent,sourceRow,sourceRow+count-1,destinationParent,destinationChild)
        for i in range(sourceRow,sourceRow-count,-1):
            self.jobs.insert(destinationChild,self.jobs[i])
            if destinationChild<i:
                self.jobs.pop(i+1)
            else: self.jobs.pop(i)
        self.endMoveRows()
        return True

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction
    def mimeData(self, list_of_QModelIndex):
        mimeData=QtCore.QMimeData()
        encodedData=QtCore.QByteArray()
        dataStream=QtCore.QDataStream(encodedData,QtCore.QIODevice.WriteOnly)
        rows=-1
        for index in list_of_QModelIndex:
            if index.isValid():
                if not index.row()==rows:
                    text= str(index.row())
                    dataStream.writeBytes(text.encode())
                    rows=index.row()
        mimeData.setData("joblist",encodedData)
        return mimeData
    def mimeTypes(self):
        return ["joblist"]
    def dropMimeData(self, QMimeData, Qt_DropAction, p_int, p_int_1, QModelIndex):
        encodedData=QMimeData.data("joblist")
        dataStream=QtCore.QDataStream(encodedData,QtCore.QIODevice.ReadOnly)
        newItems=[]
        while not dataStream.atEnd():
            # text=""
            # dataStream>>text
            # newItems<<text
            newItems+=dataStream.readBytes().decode()
        rows=len(newItems)
        count=0
        parentShift=0
        newItems=sorted(newItems)
        if int(newItems[0])<QModelIndex.row() and int(newItems[-1])>QModelIndex.row():
            return False
        else:
            for row in newItems:
                row=int(row)
                if not QModelIndex.row()+parentShift==row+count+1 and QModelIndex.isValid():
                    if QModelIndex.row()+parentShift<row+count:
                        self.moveRows(QtCore.QModelIndex(),row+count,1,QtCore.QModelIndex(),QModelIndex.row()+parentShift)
                        parentShift+=1
                    else:
                         self.moveRows(QtCore.QModelIndex(),row+count,1,QtCore.QModelIndex(),QModelIndex.row()+parentShift)
                         count-=1
        return True



class CustomDelegate(QtGui.QItemDelegate):
    def __init__(self):
        QtGui.QItemDelegate.__init__(self)
    def createEditor(self, QWidget, QStyleOptionViewItem, QModelIndex):
        if QModelIndex.column()==1:
            return(QtGui.QTimeEdit(QWidget))
        elif QModelIndex.column()==3 or  QModelIndex.column()==4:
            comboBox=QtGui.QComboBox(QWidget)
            list=["Open","Close","Disabled"]
            comboBox.addItems(list)
            return comboBox
        else:
            return(QtGui.QLineEdit(QWidget))

    def setEditorData(self, QWidget, QModelIndex):
        text=QModelIndex.model().data(QModelIndex,QtCore.Qt.DisplayRole)
        if QModelIndex.column()==1:
            if text=="Infinity": text="00:00:00"
            QWidget.setTime(QtCore.QTime.fromString(text))
        elif QModelIndex.column()==3 or QModelIndex.column()==4:
            index=QWidget.findText(text)
            QWidget.setCurrentIndex(index)
        else:
            QWidget.setText(text)
    def updateEditorGeometry(self, QWidget, QStyleOptionViewItem, QModelIndex):
        QWidget.setGeometry(QStyleOptionViewItem.rect)

class JobListWidget(QtGui.QWidget):
    throwMessage = QtCore.pyqtSignal(str, int, name='throwMessage')
    measurementFinished=QtCore.pyqtSignal( name='measurementFinsihed')

    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self)
        self.parent=parent
       #if not parent==None:
        #    self.themis=parent.themis

        self.measurementFinished.connect(self.finishMeasurement)
        self.JobListView=QtGui.QTableView()
        self.jobList=Joblist()
        self.setWindowTitle("Joblist")
        self.setObjectName("jobListWidget")
        self.JobListView.setModel(self.jobList)
        delegate=CustomDelegate()
        self.JobListView.setItemDelegate(delegate)
        self.JobListView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connect(self.JobListView,QtCore.SIGNAL("customContextMenuRequested(QPoint)"),self.contextMenu)
        self.JobListView.customContextMenuRequested.connect(self.contextMenu)
        self.JobListView.setSelectionBehavior(QtGui.QTableView.SelectRows)
        self.JobListView.setSelectionMode(QtGui.QTableView.ExtendedSelection)
        self.JobListView.setDragEnabled(True)
        self.JobListView.setDragDropMode(QtGui.QTableView.InternalMove)
        self.JobListView.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

        Buttons=QtGui.QHBoxLayout()
        self.start=QtGui.QPushButton("Start")
        self.start.setIcon(QtGui.QIcon('Bilder/accept.png'))
        self.start.clicked.connect(self.startMeasurement)
        Buttons.addWidget(self.start)
        self.pause=QtGui.QPushButton("Pause")
        self.pause.setIcon(QtGui.QIcon('Bilder/pause.png'))
        self.pause.setCheckable(True)
        self.pause.clicked.connect(self.pauseMeasurement)
        Buttons.addWidget(self.pause)
        self.stop=QtGui.QPushButton("Stop")
        self.stop.setIcon(QtGui.QIcon('Bilder/stop.png'))
        self.stop.clicked.connect(self.on_stop_clicked)
        Buttons.addWidget(self.stop)
        self.clear=QtGui.QPushButton("Clear")
        self.clear.setIcon(QtGui.QIcon('Bilder/clear.png'))
        self.clear.clicked.connect(self.clearMeasurement)
        Buttons.addWidget(self.clear)
        self.add=QtGui.QPushButton("Add")
        self.add.setIcon(QtGui.QIcon('Bilder/Plus.png'))
        self.add.clicked.connect(self.addMeasurement)
        Buttons.addWidget(self.add)

        self.timeView=QtGui.QHBoxLayout()
        self.jobListTime=QtGui.QLineEdit(self)
        self.jobListTime.setObjectName("jobListTime")
        self.jobListTime.setProperty("restore",False)
        self.jobListTime.setReadOnly(True)
        self.jobListTime.setMaximumWidth(100)
        self.jobListTime.setMinimumHeight(40)
        self.jobListTime.setText("00:00:00")
        self.jobListTime.setStyleSheet("QWidget {font-weight: bold; font-size: 15px; qproperty-alignment: 'AlignCenter | AlignCenter';}")
        l=QtGui.QLabel("Joblist Duration:")
        l.setStyleSheet("QLabel {font-weight: bold; font-size: 15px; qproperty-alignment: 'AlignCenter | AlignRight';}")
        self.timeView.addWidget(l)
        self.timeView.addWidget(self.jobListTime)
        self.timeView.addSpacerItem(QtGui.QSpacerItem(20,20,QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Fixed))
        self.bSaveJobList=QtGui.QPushButton("Save Joblist")
        self.timeView.addWidget(self.bSaveJobList)
        self.bSaveJobList.clicked.connect(self.saveJobList)
        self.bRestoreJobList=QtGui.QPushButton("Restore Joblist")
        self.timeView.addWidget(self.bRestoreJobList)
        self.bRestoreJobList.clicked.connect(self.restoreJobList)
        mainLayout=QtGui.QVBoxLayout()
        mainLayout.setMargin(2)
        mainLayout.addLayout(self.timeView)
        mainLayout.addWidget(self.JobListView)
        mainLayout.addLayout(Buttons)
        mainLayout.addWidget(self.addDialog())
        self.setLayout(mainLayout)

    def startMeasurement(self):
        if self.start.isEnabled():
            #if not self.themis.ui.startAcquisition.isEnabled():
            #    self.themis.on_stopAcquisition_clicked()
            #    self.themis.dldHandler.wait()
            self.throwMessage.emit("Start Joblist:",0)
            self.start.setEnabled(False)
            #self.jobList.measure=True ##Problems with delete first row
            #self.themis.acquisitionStopped.connect(self.startMeasurement)
        else:
            if self.jobList.rowCount()!=0:
                self.jobList.takeJob(0)
            self.updateRemainigTime()
            #self.themis.measurementItem.saveMeasurement(confirm=False)

        if self.jobList.rowCount()==0:
            self.measurementFinished.emit()
            return
        if not self.pause.isChecked():
            self.throwMessage.emit("Start Measurement:",0)
            #self.themis.startMeasurement(job=self.jobList.getJob(0))

    @QtCore.pyqtSlot()
    def saveJobList(self):
        file=str(QtGui.QFileDialog.getSaveFileName(None, "Save as...",str(os.getcwd())+"/JobLists","All Files (*)"))
        if file=="":
                return False
        with open(file, "w") as output:
            output.write(str(self.jobList.jobs))

    @QtCore.pyqtSlot()
    def restoreJobList(self):
        file=str(QtGui.QFileDialog.getOpenFileName(None, "Load Joblist",str(os.getcwd())+"/JobLists","All Files (*)"))
        if file=="":
                return False

        with open(file, "r") as input:
            jobs=input.read()
        try:
            jobs=eval(jobs)
        except:
            self.throwMessage("Error: Joblist could not be restored",0)
            self.throwMessage("--> Syntax not Valid",4)
        for job in jobs:
            self.jobList.addRow(job["filename"],job["acquisitionTime"],job["delaystage"],job["piShutter"],job["thShutter"],job["path"],job["rotationstage"])
        self.updateRemainigTime()
    @QtCore.pyqtSlot(bool)
    def finishMeasurement(self,abort=False):
        if not abort:
            self.throwMessage.emit("Joblist finished!",0)
        #self.themis.acquisitionStopped.disconnect(self.startMeasurement)
        self.start.setEnabled(True)
        self.jobList.measure=False


    def updateRemainigTime(self):
        seconds=0
        for job in self.jobList.jobs:
            s=job["acquisitionTime"]
            if s=="Infinity":
                seconds=-1
                break
            else:
                time=s.split(":")
                seconds+=int(time[0])*3600+int(time[1])*60+int(time[2])
        if seconds==-1:
            self.jobListTime.setText("Infintiy")
        else:
            self.jobListTime.setText("%02d:%02d:%02d"%(seconds/3600,seconds%3600/60,(seconds%60%60)))

    def addDialog(self):
        groupBox=QtGui.QGroupBox("")
        #groupBox=ExpanderWidget.ExpanderWidget()
        vBox=QtGui.QVBoxLayout()
        hBox=QtGui.QHBoxLayout()
        vBox.setSpacing(0)
        vBox.addWidget(QtGui.QLabel("Filename:"))
        vBox.addWidget(QtGui.QLabel("Path:"))
        vBox.addWidget(QtGui.QLabel("Measurement No (%n):"))
        vBox.addWidget(QtGui.QLabel("Add Multiple Times"))
        hBox.addLayout(vBox)

        vBox=QtGui.QVBoxLayout()
        vBox.setSpacing(0)
        self.filename=QtGui.QLineEdit()
        self.filename.setObjectName("filename")
        vBox.addWidget(self.filename)
        self.path=QtGui.QLineEdit()
        self.path.setObjectName("Path")
        vBox.addWidget(self.path)
        self.measurementNumber=QtGui.QSpinBox()
        self.measurementNumber.setMaximum(99999)
        self.measurementNumber.setValue(1)
        vBox.addWidget(self.measurementNumber)
        self.addMultiple=QtGui.QSpinBox()
        self.addMultiple.setMinimum(1)
        self.addMultiple.setMaximum(99999)
        self.addMultiple.setValue(1)
        self.addMultiple.setObjectName("addMultiple")
        vBox.addWidget(self.addMultiple)
        hBox.addLayout(vBox)

        vBox=QtGui.QVBoxLayout()
        vBox.setSpacing(0)
        vBox.addWidget(QtGui.QLabel("Acquisition Time (%t):"))
        vBox.addWidget(QtGui.QLabel("DelayStage (%d):"))
        vBox.addWidget(QtGui.QLabel("RotationStage (%r):"))
        vBox.addWidget(QtGui.QLabel("Shutter (%piShut/%thShut):"))
        hBox.addLayout(vBox)

        vBox=QtGui.QVBoxLayout()
        vBox.setSpacing(0)
        self.acquisitionTime=QtGui.QTimeEdit()
        self.acquisitionTime.setObjectName("acquisitionTime")
        #self.acquisitionTime.setMinimumTime(QtCore.QTime.fromString("00:00:01"))
        vBox.addWidget(self.acquisitionTime)
        self.delaystage=QtGui.QLineEdit()
        self.delaystage.setObjectName("DelayStage")
        vBox.addWidget(self.delaystage)
        self.rotationstage=QtGui.QLineEdit()
        self.rotationstage.setObjectName("RotationStage")
        vBox.addWidget(self.rotationstage)
        self.mode=QtGui.QLineEdit()
        self.mode.setObjectName("Shutter")
        self.mode.setToolTip("Valid Input:\npiOpen/piClose = set Picard Shutter Opend/Closed\nthOpen/thClose = set Thorlabs Shutter Opend or Closed \n"
                             "The shutter will be disabled automatically, if there is no value for it. \nSeparate mesurements with comma \nExample coomand: (piOpen|thClose),thOpen")
        vBox.addWidget(self.mode)
        hBox.addLayout(vBox)



        groupBox.setLayout(hBox)
        expander=ExpanderWidget.ExpanderWidget()
        expander.setMaximumHeight(170)
        expander.addWidget(groupBox)
        #expander.addLayout(hBox)
        expander.setText("Define jobs")
        #expander.setExpanded(True)
        return(expander)

    def getPath(self):
        path=str(self.path.text())
        if "Default:" in path:
            list=path.split(":")
            if len(list)<3: list.append("")
        else:
            list=[path]
        return list

    def pauseMeasurement(self):
        if self.start.isEnabled():
            self.pause.setChecked(False)
            return
        #if not self.pause.isChecked() #and self.parent.themis.ui.startAcquisition.isEnabled()==True:
            #self.themis.startMeasurement(job=self.jobList.getJob(0))

    #@QtCore.pyqtSlot()
    def on_stop_clicked(self):
        if not self.start.isEnabled():
            self.throwMessage.emit("Measurement stopped!:",0)
            #self.themis.acquisitionStopped.disconnect(self.startMeasurement)
            self.start.setEnabled(True)
            self.jobList.measure=False
        #self.themis.on_stopAcquisition_clicked()

    def clearMeasurement(self):
        self.jobList.clear()
        self.updateRemainigTime()
    def addMeasurement(self):
        for i in range(self.addMultiple.value()):
            positions=self.getDelaystagePositions()
            rotationPos=self.getRotationstagePositions()
            shutterModes=self.getModes()
            acquisitionTime=self.acquisitionTime.time().toString()

            #if acquisitionTime=="00:00:00": acquisitionTime="00:05:00"
            for delay in positions:
                for rot in rotationPos:
                    for shutter in shutterModes:
                        filename=str(self.filename.text())
                        if not delay=="Disabled": filename=filename.replace("%d",("%08.4f"% delay))
                        else: filename=filename.replace("%d","")
                        if not rot=="Disabled": filename=filename.replace("%r",("%08.4f"% rot))
                        else: filename=filename.replace("%r","")
                        if not shutter[0]=="Disabled": filename=filename.replace("%piShut",shutter[0])
                        else: filename=filename.replace("%piShut","")
                        if not shutter[1]=="Disabled": filename=filename.replace("%thShut",shutter[1])
                        else: filename=filename.replace("%thShut","")
                        #filename=filename.replace("%n",("%03d"% self.measurementNumber.value()))
                        seconds=acquisitionTime.split(":")
                        seconds=int(seconds[0])*3600+int(seconds[1])*60+int(seconds[2])
                        filename=filename.replace("%t",str(seconds))
                        self.jobList.addRow(filename,acquisitionTime,delay,shutter[0],shutter[1],self.getPath(),rot)
                        #self.measurementNumber.setValue(self.measurementNumber.value()+1)
                #self.JobListView.resizeColumnsToContents()
        self.updateRemainigTime()

    #def createFileName(self,job):
    #    filename=str(job["filename"])
    #    delay=job["delayStage"]
    #    if not delay=="Disabled": filename=filename.replace("%d",("%08.4f"% delay))
    #    else: filename=filename.replace("%d","")
    #    rot=job["rotationstage"]
    #    if not rot=="Disabled": filename=filename.replace("%r",("%08.4f"% rot))
    #    else: filename=filename.replace("%r","")
    #    piShut=job["piShutter"]
    #    if not piShut=="Disabled": filename=filename.replace("%piShut",piShut)
    #    else: filename=filename.replace("%piShut","")
    #    thShut=job["thShutter"]
    #    if not thShut=="Disabled": filename=filename.replace("%thShut",thShut)
    #    else: filename=filename.replace("%thShut","")
    #    #filename=filename.replace("%n",("%03d"% self.measurementNumber.value()))
    #    return filename

    def getRotationstagePositions(self):
        expression=self.rotationstage.text()
        if expression=="":return ["Disabled"]
        result=[]
        try:
            if "," in expression:
                list=expression.split(",")
            else: list=[expression]
            for i in range(len(list)):
                text=list[i]
                if ":" in text:
                    if "@" in text:
                        list1=text.split("@")[0].split(":")
                        mode=text.split("@")[1]
                        if mode=="linear":
                            result=np.append(result,np.linspace(float(list1[0]),float(list1[1]),list1[2]))
                        elif mode=="log":
                            res=np.linspace(np.log10(float(list1[0])),np.log10(float(list1[1])),list1[2])
                            result=np.append(result, np.power(10,res))
                        else:
                            raise ValueError
                    else:
                        list1=text.split(":")
                        result=np.append(result, np.arange(float(list1[0]),float(list1[1])+float(list1[2])/10000,float(list1[2])))
                else:
                    value=float(text)
                    result=np.append(result, [value])

            return result
        except(Exception):
            self.throwMessage.emit("Cannot Parse the RotationStage positions",0)
            self.throwMessage.emit("Valid Input: start:stop:stepwidth (eg: 5:15:5)",2)
            self.throwMessage.emit("             position (eg: 200)",2)
            self.throwMessage.emit("             start:stop:steps@mode (eg: 5:15:3@linear or 5:15:3@log)",2)
            self.throwMessage.emit("             expressions can be concatonated with \",\" (eg: 2,4,3:10:4,5) ",2)

    def getDelaystagePositions(self):
        expression=self.delaystage.text()
        if expression=="":return ["Disabled"]
        result=[]
        try:
            if "," in expression:
                list=expression.split(",")
            else: list=[expression]
            for i in range(len(list)):
                text=list[i]
                if ":" in text:
                    if "@" in text:
                        list1=text.split("@")[0].split(":")
                        mode=text.split("@")[1]
                        if mode=="linear":
                            result=np.append(result,np.linspace(float(list1[0]),float(list1[1]),list1[2]))
                        elif mode=="log":
                            res=np.linspace(np.log10(float(list1[0])),np.log10(float(list1[1])),list1[2])
                            result=np.append(result, np.power(10,res))
                        else:
                            raise ValueError
                    else:
                        list1=text.split(":")
                        result=np.append(result, np.arange(float(list1[0]),float(list1[1])+float(list1[2])/10000,float(list1[2])))
                else:
                    value=float(text)
                    result=np.append(result, [value])

            return result

        except(Exception):
            self.throwMessage.emit("Cannot Parse the DelayStage positions",0)
            self.throwMessage.emit("Valid Input: start:stop:stepwidth (eg: 5:15:5)",2)
            self.throwMessage.emit("             position (eg: 200)",2)
            self.throwMessage.emit("             start:stop:steps@mode (eg: 5:15:3@linear or 5:15:3@log)",2)
            self.throwMessage.emit("             expressions can be concatonated with \",\" (eg: 2,4,3:10:4,5) ",2)
            
    def getModes(self):
        text=self.mode.text()
        if text=="": return [("Disabled","Disabled")]
        modes=[]
        try:
            if "," in text:
                list=text.split(",")
            else:
                list=[text]
            for i in range(len(list)):
                mode=list[i]
                if "piopen" in mode.lower(): piShut="Open"
                elif "piclose" in mode.lower(): piShut="Close"
                else: piShut="Disabled"
                if "thopen" in mode.lower(): thShut="Open"
                elif "thclose" in mode.lower(): thShut="Close"
                else: thShut="Disabled"
                modes.append((piShut,thShut))
            return(modes)
        except(ValueError):
            self.throwMessage.emit("Cannot Parse the Shutter options",0)


    def contextMenu(self,point):
        self.menu=QtGui.QMenu()
        self.menu.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        delete=QtGui.QAction("Delete",self.menu)
        delete.triggered.connect(self.deleteSelection)
        self.menu.addAction(delete)

        self.menu.popup(self.JobListView.mapToGlobal(point))

    def deleteSelection(self):
        if self.jobList.measure: i=1
        else: i=0
        deleted=0
        for i in range(self.jobList.rowCount()):
            if self.JobListView.selectionModel().isRowSelected(i-deleted,QtCore.QModelIndex()):
                self.jobList.removeRow(i-deleted,QtCore.QModelIndex())
                deleted+=1
        self.updateRemainigTime()

def printMsg(text,pos):
    pass
    #print text
if __name__=="__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    joblist=JobListWidget()
    joblist.throwMessage.connect(printMsg)
    joblist.show()
    app.exec_()
    sys.exit()
