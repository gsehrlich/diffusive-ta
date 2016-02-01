# -*- coding: utf-8 -*-

from pyqtgraph.Qt import QtCore, QtGui


from PyQt4.QtCore import *
from PyQt4.QtGui import *
from Daniel.SpinBox import SpinBox
from collections import OrderedDict
import pyqtgraph.parametertree.parameterTypes as pTypes
import pickle
from pyqtgraph.parametertree import Parameter, ParameterTree
import tables
import PyQt4
from Daniel.ExpanderWidget import ExpanderWidget

def updateDefaultButton():
    pass
class Config(QScrollArea):
    def __init__(self):
        QScrollArea.__init__(self)
        self.setWidget()

class Item(QWidget):
    def __init__(self,opts,parent=None):
        QWidget.__init__(self,parent)
        self.mainLayout=QVBoxLayout()
        if isinstance(parent,Item):
            self.parentItem=parent
            self.labelSizes=self.parentItem.labelSizes
            self.parentItem.label.installEventFilter(self)
            self.size=12
        else:
            self.parentItem=None
            self.labelSizes={}
        self.name=opts["name"]
        #self.color=self.palette().color(self.backgroundRole())
        #self.color=str(self.color.red())+","+str(self.color.green())+","+str(self.color.blue())
        self.setContentsMargins(0,0,0,0)
        self.setObjectName(self.name)
        if not "title" in opts:
            self.title=self.name
        else:
            self.title=opts["title"]
        if not "type" in opts:
            self.type="container"
        else:
            self.type=opts["type"]
        # if "color" in opts:
        #     rgb=opts["color"].split(",")
        #     if len(rgb)==3:
        #         rgb+="256"
        #     self.color=QColor.fromRgb(int(rgb[0]),int(rgb[1]),int(rgb[2]))
        # else:
        #     self.color=""
        self.children={}

        if "color" in opts:
                color="background-color:"+opts["color"]+";"
        else: color=""
        if "size"in opts:
            size="font:"+opts["size"]
        else:  size="font: 12px"

        self.label =QPushButton(self)
        self.label.setText(self.title)
        self.label.setFlat(True)
        self.setStyleSheet("text-align: left;"+size+";")
        self.label.setStyleSheet("text-align: left; font-weight: bold; border: none;"+color+size)
        self.labelSizes[self]= self.label.fontMetrics().boundingRect(self.label.text()).width()

        self.hBox=QHBoxLayout()
        self.hBox.addWidget(self.label)
        self.hBox.setSpacing(5)
        self.mainLayout.addLayout(self.hBox)
        self.mainLayout.setContentsMargins(0,0,0,0)
        self.mainLayout.setSpacing(0)
        self.setLayout(self.mainLayout)
        self.mainLayout.addSpacerItem(QSpacerItem(0,0,QSizePolicy.Expanding,QSizePolicy.Expanding))

        if self.type!="container":
            self.widget=self.createWidget(self.title,self.type,opts)
            self.hBox.addWidget(self.widget)
        else:
            self.widget=None
        if "children" in opts:
            for child in opts["children"]:
                self.addItem(Item(child,parent=self))
        if self.parentItem==None:
            pass



        if hasattr(self,"cover"): self.cover.setPalette(self.palette())

    def addItem(self,item,pos=None):
        if self.children=={}:
            self.label.setIcon(QIcon("Bilder/arrow-expanded.png"))
            self.label.clicked.connect(self.toogleExpanded)
            self.expanded=True
            self.childrenWidget=QWidget(self)
            self.childrenWidget.setContentsMargins(20,0,0,0)
            self.mainLayout.insertWidget(1,self.childrenWidget)
            self.childrenLayout=QVBoxLayout()
            self.childrenLayout.setContentsMargins(0,0,0,0)
            self.childrenLayout.setSpacing(0)
            self.childrenWidget.setLayout(self.childrenLayout)
            self.childrenLayout.addSpacerItem(QSpacerItem(0,0,QSizePolicy.Expanding,QSizePolicy.Expanding))

        if item.name in self.children:
            raise ValueError("Item already has a child with name:"+ item.name)
        else:
            self.children[item.name]=item
            if pos==None:
                self.childrenLayout.insertWidget(self.childrenLayout.count()-1,item)
            else:
                self.childrenLayout.insertWidget(pos,item)


    def toogleExpanded(self):
        self.setExpanded(not self.expanded)

    def setExpanded(self,expand):
        if expand==False:
            self.expanded = False
            self.label.setIcon(QIcon("Bilder/arrow.png"))

            size = self.mainLayout.sizeHint()
            width = size.width()
            height = size.height()
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            self.childrenWidget.hide()
            self.resize(width, 20)
            self.updateGeometry()

        else:
            self.expanded = True
            self.label.setIcon(QIcon("Bilder/arrow-expanded.png"))
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.childrenWidget.show()
            self.updateGeometry()

    def eventFilter(self, object, ev):
        if object==self.parentItem.label and ev.type()==QEvent.Resize:
            if self.label.width()<ev.size().width()-20:
                pass
                #self.label.setFixedWidth()
        elif object==self.widget and ev.type()==QEvent.Resize:
            if hasattr(self,"cover"):
                self.cover.resize(ev.size())
        elif ev.type()==QEvent.FocusIn:
            self.focusInEvent(ev)
        elif ev.type()==QEvent.FocusOut:
            self.focusOutEvent(ev)
            return(object.eventFilter(object,ev))

        return(object.eventFilter(object,ev))

    def focusInEvent(self, QFocusEvent):
        if hasattr(self,"cover"):
            self.cover.hide()
    def focusOutEvent(self, QFocusEvent):
        if hasattr(self,"cover"):
            if self.type=="float" or self.type=="int":
                self.cover.setText(self.widget.lineEdit().text())
            if self.type=="str":
                self.cover.setText(self.widget.text())
            self.cover.show()
    def value(self):
        if self.type=="int" or self.type=="float":
            return self.widget.value()
        elif self.type=="str":
             return self.widget.text()
        else:
            raise NotImplementedError

    def setValue(self,value):
        if self.type=="int" or self.type=="float":
            self.widget.setValue(value)
        elif self.type=="str":
            self.widget.setText(value)
        else:
            raise NotImplementedError


    def getHeadItem(self,item=None):
        if item==None:
            item=self
        if item.parentItem==None:
            return(self)
        else:
            return(self.getHeadItem(item.parentItem))

    def getItem(self,*names):
        """Return a child parameter.
        Accepts the name of the child or a tuple (path, to, child)"""
        try:
            child = self.children[names[0]]
        except KeyError:
            raise Exception("Parameter %s has no child named %s" % (self.name, names[0]))

        if len(names) > 1:
            return child.getItem(*names[1:])
        else:
            return child


    def __getitem__(self, names):
        """Get the value of a child parameter. The name may also be a tuple giving
        the path to a sub-parameter::

            value = param[('child', 'grandchild')]
        """
        if not isinstance(names, tuple):
            names = (names,)
        return self.getItem(*names).value()

    def __setitem__(self, names, value):
        """Set the value of a child parameter. The name may also be a tuple giving
        the path to a sub-parameter::

            param[('child', 'grandchild')] = value
        """
        if isinstance(names, str):
            names = (names,)
        return self.getItem(*names).setValue(value)

    def createWidget(self,title,type,opts):
        if type=="float" or type=="int":
            if type=="int": opts["int"]=True
            widget=SpinBox(self,**opts)
            self.cover=QLabel(widget)
            self.cover.setText(widget.lineEdit().text())


        elif type=="str":
            widget=QLineEdit(self)
            if "value" in opts:
                widget.setText(opts["value"])
            self.cover=QLabel(widget)


            self.cover.setText(widget.text())

        widget.installEventFilter(self)
        if hasattr(self,"cover"):
            self.cover.setContentsMargins(2,2,2,2)
            self.cover.setGeometry(widget.geometry())
            #self.cover.setGeometry(0,0,widget.width(),widget.height())
            self.cover.setAutoFillBackground(True)
            self.cover.setStyleSheet(self.styleSheet()+"background-color:rgb"+str(self.cover.palette().color(QPalette.Background).getRgb())[:-6]+");")
            #self.cover.setStyleSheet("QLineEdit {background:rgb(240,100,240)};")
           # print(self.styleSheet()+" background-color:rgb"+str(self.cover.palette().color(QPalette.Background).getRgb())[:-6]+");")

            self.cover.installEventFilter(self)
        widget.installEventFilter(self)

        return widget



class ConfigWidget1(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        t = Item({"name":"cofig","color":"rgb(0,102,204)","size":"15px","children":[
                        {"name":"Versuch1","type":"str","value":"hallo"},
                        {"name":"Versuch2","type":"str","value":"hallo2","children":[
                            {"name":"Versuch3","type":"int","value":4},
                            {"name":"Versuch4","type":"float","value":15,"suffix":" nA","min":15,"max":50,"ReadOnly":True},
                        ]},
                        {"name":"Versuch3","type":"int","value":4},
                        {"name":"Versuch4","type":"float","value":15,"suffix":" nA","min":15,"max":50,"ReadOnly":True},
                        {"name":"cofig2asdasdss","color":"rgb(202,225,255)","size":"15px","children":[
                            {"name":"Versuch5","type":"str","value":"hallo"},
                            {"name":"Versuch623244","type":"str","value":"hallo2"},
                            {"name":"Versuch7","type":"int","value":4},
                            {"name":"Versuch2","type":"float","value":15,"suffix":" nA","min":15,"max":50,"ReadOnly":True}
                            ]}
                         ]
        })
        layout=QVBoxLayout()
        #t["expander1","LineEdit"]="Gosejohan"
        #print t["expander1","LineEdit"]
        layout.addWidget(t)
        layout.setContentsMargins(0,0,0,0)
        self.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

    def insertWidget(self,layout,widget):
        pass


## test subclassing parameters
## This parameter automatically generates two child parameters which are always reciprocals of each other
class ComplexParameter(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'bool'
        opts['value'] = True
        pTypes.GroupParameter.__init__(self, **opts)

        self.addChild({'name': 'A = 1/B', 'type': 'float', 'value': 7, 'suffix': 'Hz', 'siPrefix': True})
        self.addChild({'name': 'B = 1/A', 'type': 'float', 'value': 1/7., 'suffix': 's', 'siPrefix': True})
        self.a = self.param('A = 1/B')
        self.b = self.param('B = 1/A')
        self.a.sigValueChanged.connect(self.aChanged)
        self.b.sigValueChanged.connect(self.bChanged)

    def aChanged(self):
        self.b.setValue(1.0 / self.a.value(), blockSignal=self.bChanged)

    def bChanged(self):
        self.a.setValue(1.0 / self.b.value(), blockSignal=self.aChanged)


## test add/remove
## this group includes a menu allowing the user to add new parameters into its child list
class ScalableGroup(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add Attribute"
        pTypes.GroupParameter.__init__(self, **opts)

    def addNew(self):
        name, ok = QtGui.QInputDialog.getText(None, 'Add Item', 'Enter your name:')
        if ok:
            self.addChild(dict(name=str(name), type="str", value="", removable=True, renamable=True))
    def add(self,name,value,type="str"):
        self.addChild(dict(name=name,type=type,value=value, removable=True, renamable=True))



## Create tree of Parameter objects
class configurationWidget(ParameterTree):
    sigConfigChanged=QtCore.pyqtSignal(str,object)
    def __init__(self,dataSet=None):
        self.dataSet=dataSet
        ParameterTree.__init__(self)
        self.setObjectName("ConfigurationWidget")
        self.setWindowTitle("Measurement Configuration")
        self.setParams()
        self.p.sigTreeStateChanged.connect(self.change)
        self.connections=[]

        self.p.param("File Configuration","Folder").sigValueChanged.connect(self.folderModeChanged)

    def folderModeChanged(self,value):
        if value.value()=="Default":
            self.p.param("File Configuration","Folder","Beamtime").show(True)
            self.p.param("File Configuration","Folder","Groupname").show(True)
            self.p.param("File Configuration","Folder","Custom Folder").show(False)
        else:
            self.p.param("File Configuration","Folder","Beamtime").show(False)
            self.p.param("File Configuration","Folder","Groupname").show(False)
            self.p.param("File Configuration","Folder","Custom Folder").show(True)

    def connectSignal(self,signal,slot):
        signal.connect(slot)
        self.connections.append((signal,slot))

    def blockSignals2(self,blockAll=True):
        if blockAll:
            for signal,slot in self.connections:
                signal.disconnect(slot)
        else:
            for signal,slot in self.connections:
                signal.connect(slot)
    def toDict(self,param=None,result=None):
        if param==None:
            result={}
            param=self.p
        path = str(self.p.childPath(param)).replace("\'","").replace(", ","/")[1:-1]

        result[path]=param.value()
        for child in param.children():
            self.toDict(child,result)
        return(result)






    def setDelayStage(self,position):
        self.p["Measurement Info","Delaystage"]=position
    def setPiShutterState(self,state):
        self.p["Measurement Info","Picard Shutter"]=state
    def setThShutterState(self,state):
        self.p["Measurement Info","Picard Shutter"]=state
    def setRotationStagePosition(self,position):
         self.p["Measurement Info","Rotationstage"]=position

    def restoreState(self,h5file,removeChildren=False,file=None):
        self.blockSignals2(True)

        state=h5file.root._v_attrs.config

        if not isinstance(state,str):
            h5file.close()
            import subprocess
            import os
            path=os.environ["WinPython"]
            subprocess.check_call([path+"\\pythonw.exe",path+r"\Lib\site-packages\Daniel\unpickleOldApi.py",file], shell=True)
            h5file=tables.openFile(file,mode="r")
            state=h5file.root._v_attrs.config
        state=state.replace("PyQt4.QtCore.QString('Closed')","'Closed'")
        state=state.replace("PyQt4.QtCore.QString('Opend')","'Opend'")
        #print (str(state))
        state=eval(str(state))

        self.p.restoreState(state,blockSignals=True,addChildren=True, removeChildren=False)
        self.blockSignals2(False)
        return (h5file)


    def setParams(self):
        DLLParams= {'name': 'DLLParams', 'type': 'group',"expaned":False, 'children': [
                {'name': 'X factor', 'type': 'float', 'value': 0.022,'readonly': True},
                {'name': 'Y factor', 'type': 'float', 'value': 0.024,'readonly': True},
                {'name': 'T factor', 'type': 'float', 'value': 0.0068587,'readonly': True},
                {'name': 'X offset', 'type': 'float', 'value': 11.264,'readonly': True},
                {'name': 'Y offset', 'type': 'float', 'value': 12.288,'readonly': True},
                {'name': 'T offset', 'type': 'float', 'value': 0,'readonly': True},
                {'name': 'EX factor', 'type': 'float', 'value': 1,'readonly': True,"visible":False},
                {'name': 'EY factor', 'type': 'float', 'value': 1,'readonly': True},
                {'name': 'E factor', 'type': 'float', 'value': 1,'readonly': True},
                {'name': 'EX offset', 'type': 'float', 'value': 1,'readonly': True},
                {'name': 'EY offset', 'type': 'float', 'value': 1,'readonly': True},
                {'name': 'E offset', 'type': 'float', 'value': 1,'readonly': True},
                {'name': 'X Min', 'type': 'float', 'value': -16},
                {'name': 'X Max', 'type': 'float', 'value': 16},
                {'name': 'Y Min', 'type': 'float', 'value': -16},
                {'name': 'Y Max', 'type': 'float', 'value': 16}
                ]}
        themisParams= {'name': 'Themis Parameter', 'type': 'group',"expaned":False, 'children': [
                {'name': 'Lensmode', 'type': 'str', 'value': "DriftMode:100V",'readonly': True},
                {'name': 'Kinetic Energy', 'type': 'float', 'value': 20,'readonly': True, 'suffix': 'eV', 'siPrefix': True},
                {'name': 'Pass Energy', 'type': 'float', 'value': 20,'readonly': True, 'suffix': 'eV', 'siPrefix': True},
                {'name': 'Conversion Voltage', 'type': 'float', 'value': 0,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'Aux Voltage', 'type': 'float', 'value': 0,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'Suction Voltage', 'type': 'float', 'value': 0,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'Workfunction', 'type': 'float', 'value': 0,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'Detector Voltage', 'type': 'float', 'value': 1950,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'DLD Voltage', 'type': 'float', 'value': 400,'readonly': True, 'suffix': 'V', 'siPrefix': True},
                {'name': 'Timezero', 'type': 'float', 'value': 600, 'suffix': ' ns'}
                ]}
        measurementInfo=ScalableGroup(name="Measurement Info", children=[
                {'name': 'Sample', 'type': 'str', 'value': "not specified"},
                {'name': 'Begin of Acquisition', 'type': 'str', 'value': "not set", "readonly":True},
                {'name': 'End of Acquisition', 'type': 'str', 'value': "not yet finished", "readonly":True},
                {'name': 'Delaystage', 'type': 'float', 'value': 0, 'suffix': 'mm','removable': False},
                {'name': 'Rotationstage', 'type': 'float', 'value': 0, 'suffix': '°','removable': False},
                {'name': 'Thorlabs Shutter', 'type': 'str', 'value': "Unknown",'removable': False},
                {'name': 'Picard Shutter', 'type': 'str', 'value': "Unknown",'removable': False},
                {'name': 'Helmholtz coils', 'type': 'group', "expanded":False, 'children': [
                    {'name': 'Beam-axis', 'type': 'float', 'value': 0, 'suffix': 'A', 'siPrefix': True},
                    {'name': 'TOF-Axis Hutch', 'type': 'float', 'value': 0, 'suffix': 'A', 'siPrefix': True},
                    {'name': 'TOF-Axis Turbo', 'type': 'float', 'value': 0, 'suffix': 'A', 'siPrefix': True},
                    {'name': 'Z-Axis', 'type': 'float', 'value': 0, 'suffix': 'A', 'siPrefix': True},
                ]},
                {'name': 'Comment', 'type': 'text', "expanded":False, 'value': ''}
            ])
        fileInfo={'name': "File Configuration", 'type': 'group', 'children': [
                {'name': 'Save Measurement', 'type': 'action'},
                {'name': 'Filename', 'type': 'str','value':"" },
                {'name': 'Folder', 'type': 'list', 'values': ["Default","Custom"], 'value': "Default","children":[
                    {'name': 'Beamtime', 'type': 'str', 'value': ""},
                    {'name': 'Groupname', 'type': 'str', 'value': ""},
                    {'name': 'Custom Folder', 'type': 'str', 'value': "","visible":False},
                ]},
                {'name': 'Copy to Grouphome', 'type': 'bool', 'value': True
                },
                {'name': 'Save raw data', 'type': 'bool', 'value': True},
                {'name': 'Save spectra', 'type': 'bool', 'value': True}
            ]}
        spectra={'name': 'Spectra', 'type': 'group', 'children': [
            {'name': 'Rotate MCP', 'type': 'float', 'value': 0, 'suffix': ' deg'},
            {'name': 'Exposure Time (s)', 'type': 'float', 'value': 0.2,'readonly':True},
            {'name': 'Gui Update Time (s)', 'type': 'float', 'value': 1},
            {'name': 'Time Histogram', 'type': 'group', "expanded":True, 'children': [
                {'name': 'Time min', 'type': 'float', 'value': 1100, 'suffix': ' ns'},
                {'name': 'Time max', 'type': 'float', 'value': 2000, 'suffix': ' ns'},
                {'name': 'Time resolution', 'type': 'float', 'value': 0.1, 'suffix': ' ns'},
                ]},
            {'name': 'Time Image', 'type': 'group', "expanded":False, 'children': [
                {'name': 'Xbins', 'type': 'int', 'value': 128},
                {'name': 'Ybins', 'type': 'int', 'value': 128},
                ]},
            {'name': 'Energy Histogram', 'type': 'group', "expanded":True, 'children': [
                {'name': 'Energy min', 'type': 'float', 'value': 0.1, 'suffix': 'eV',"readonly":False},
                {'name': 'Energy max', 'type': 'float', 'value': 40, 'suffix': 'eV',"readonly":False},
                {'name': 'Energy resolution', 'type': 'float', 'value': 0.01, 'suffix': ' eV'},
                {'name': 'Angle max', 'type': 'float', 'value': 10}
                ]},
            {'name': 'Energy Image', 'type': 'group', "expanded":False, 'children': [
                {'name': 'Xbins', 'type': 'int', 'value': 128},
                {'name': 'Ybins', 'type': 'int', 'value': 128}
                ]},
            {"name":"Create new Conversion", "type":"action"}
            ]}

        self.p = Parameter.create(name='params', type='group', children=[fileInfo,measurementInfo,spectra,themisParams,DLLParams])
        self.setParameters(self.p, showTop=False)




    def addParameters(self, param, root=None, depth=0, showTop=True):
        item = param.makeTreeItem(depth=depth)
        try:
            #item.defaultBtn.setParent(None)
            #item.layoutWidget.layout().removeWidget(item.defaultBtn)
            item.updateDefaultBtn=updateDefaultButton
            item.defaultBtn.hide()
        except(AttributeError):
            pass

        if root is None:
            root = self.invisibleRootItem()
            ## Hide top-level item
            if not showTop:
                item.setText(0, '')
                item.setSizeHint(0, QtCore.QSize(1,1))
                item.setSizeHint(1, QtCore.QSize(1,1))
                depth -= 1
        root.addChild(item)
        item.treeWidgetChanged()


        for ch in param:
            self.addParameters(ch, root=item, depth=depth+1)

    def setDLLParams(self,factors,offsets,pxLimits):
        self.p["DLLParams","X factor"]=factors[0]
        self.p["DLLParams","Y factor"]=factors[1]
        self.p["DLLParams","T factor"]=factors[2]
        self.p["DLLParams","X offset"]=offsets[0]
        self.p["DLLParams","Y offset"]=offsets[1]
        self.p["DLLParams","T offset"]=offsets[2]

    def setEnergyParams(self,factors,offsets):
        self.p["DLLParams","EX factor"]=factors[0]
        self.p["DLLParams","EY factor"]=factors[1]
        self.p["DLLParams","E factor"]=factors[2]
        self.p["DLLParams","EX offset"]=offsets[0]
        self.p["DLLParams","EY offset"]=offsets[1]
        self.p["DLLParams","E offset"]=offsets[2]




## If anything changes in the tree, print a message
    def change(self,param, changes):
        for param, change, data in changes:
            if change=="value":
                path = str(self.p.childPath(param)).replace("\'","").replace(", ","/")[1:-1]
                self.sigConfigChanged.emit(path,data)
        # print("tree changes:")
        # for param, change, data in changes:
        #     path = self.p.childPath(param)
        #     if path is not None:
        #         childName = '.'.join(path)
        #     else:
        #         childName = param.name()
        #     print('  parameter: %s'% childName)
        #     print('  change:    %s'% change)
        #     print('  data:      %s'% str(data))
        #     print('  ----------')
       # if (childName=="Spectra.Energy Histogram.Show"):
        #    win=self.view.viewer.getDock("Energy")
         #   if data:
          #      win._container.setVisible(True)
           # else:
            #    win._container.setVisible(False)



## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    app = QtGui.QApplication([])
    import sys
    #t=Item({"name":"expander","title":"Versuch","type":"int","value":5,"unit":"ns"})
    #t=configurationWidget()
    t=ConfigWidget1()
    #print(t.layout())
    #t.resize(300,800)
    t.show()


    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
