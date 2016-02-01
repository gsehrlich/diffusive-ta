from tables import *
import os.path
from PyQt4 import QtGui
import datetime


def checkFileHasGroup(file, name):
        for group in file.walkNodes():
            if group._v_name == name:
                return True
        return False

def checkIfFileExists(file):
        return os.path.exists(file)

def checkIfPathExist(dir,create=True):
        if not os.path.exists(dir):
            if create:
                try:
                    os.makedirs(dir)
                    return True
                except(WindowsError):
                    return(False)
            else: return False
        else: return True

def createDefaultPath(beamtime,groupname):
    now=datetime.datetime.now()
    if not groupname=="": groupname="/"+groupname
    if not beamtime=="": beamtime=beamtime+"/"
    path="C:/Data/Measurements/TAS-DATA/FU_%d/"%(now.year) + beamtime+now.strftime("%Y-%m-%d")+groupname
    return (path)

def fileOverwriteDialog(file,path="C:/"):
        msgBox=QtGui.QMessageBox()
        msgBox.setText("The File "+file+" already exist!")
        msgBox.setInformativeText("How do you want to proceed?")
        msgBox.addButton("Save as", QtGui.QMessageBox.YesRole)
        msgBox.addButton("Don't Save",  QtGui.QMessageBox.NoRole)
        msgBox.addButton("Replace",  QtGui.QMessageBox.AcceptRole)
        msgBox.setIcon(QtGui.QMessageBox.Warning)
        ret=msgBox.exec_()
        if(ret==0):
            file=str(QtGui.QFileDialog.getSaveFileName(None, "Save as...", path,"All Files (*)"))
            if file=="":
                return None
        if(ret==1):
            file=None
        return(file)




