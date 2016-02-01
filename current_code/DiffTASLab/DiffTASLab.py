import sys
import warnings
import traceback
import sys
import warnings
import traceback
from PyQt4 import QtGui, QtCore, uic
from PyQt4.QtCore import QCoreApplication
from chopper_copy import ChopperControls
from delaystage import DelayStageWidget
from JoblistTAS import JobListWidget
from ThorlabsBeamshutter import BeamshutterWidget
from andor.andorcamera import Newton01, iDus01
from MeasurementItem import DataViewer
#from cam_control import CameraControlWidget
#from acq_control import AcquisitionWidget
from dataAcquirerSpectral import DataAcquirerSpectral
from plotterSpectral1D import PlotterWidgetSpectral1D
from andorCamSpec import AndorCamSpecWidget

# debug
import time, datetime

#global start_w, rms_w, ratio_w, probe_only_w, pump_probe_w
cams = [Newton01, iDus01]
specs = []
specs_aux = []
#cam  = cams[1]
dflt_x = range(1, 513)


class DiffTASLab(DataViewer):
    cam_initialize_done = QtCore.pyqtSignal(int, int)
    spec_initialize     = QtCore.pyqtSignal()
    cam_initialize      = QtCore.pyqtSignal()
        
    def __init__(self):
        super(DiffTASLab, self).__init__(parent=None)
        self.cam_initialize_done.connect(self.init_UI)
        self.init_andor_devices()
        #self.init_UI()

    def init_andor_devices(self):
        """Initialize all Andor devices (Cameras, Spectrograph). 
        Do not proceed before initializition is finished."""
        # self.spec_initialize.connect(self.cam.spec.initialize,
        #     type=QtCore.Qt.BlockingQueuedConnection)
        # self.cam_initialize.connect(self.cam.initialize,
        #     type=QtCore.Qt.BlockingQueuedConnection)
        
        for actcam in cams:
            # print("Connecting cam: " + actcam.name + "\n")
            # self.cam_initialize.connect(actcam.initialize,
            #                             type=QtCore.Qt.DirectConnection)
            # print("Connecting spec: " + actcam.name + "\n")
            # self.spec_initialize.connect(actcam.spec.initialize,
            #                             type=QtCore.Qt.DirectConnection)
            # #print("Init cam: " + actcam.name + "\n")
            # self.cam_initialize.emit()
            # print("Init spec: " + actcam.name + "\n")
            # self.spec_initialize.emit()
            print("Init camera: " + actcam.name + "\n")
            actcam.initialize()
            specs_aux.append(actcam.spec)


        for actspec in specs_aux:
            if len(specs) == 0:
                specs.append(actspec)
            else:
                duplicate_spec = False
                for sp in specs:
                    if actspec.serial == sp.serial:
                        duplicate_spec = True
                if not duplicate_spec:
                    specs.append(actspec)

        for actspec in specs:
            print("Init spectrograph: " + actspec.name + "\n")
            actspec.initialize()
            
        print("Finished\n")
        self.cam_initialize_done.emit(0, 0)


    def init_UI(self, cam_id, spec_id):
        cam  = cams[cam_id]
        spec = specs[spec_id]
        #print(str(cam.x[0]) + str(cam.x[-1]) + "\n")
        mode = "running"
        #mode = "blockwise"
        #self.resize(800, 800)
        #self.showMaximized()
        self.showNormal()
        #self.devices = {}
        self.Devices        = DataViewer(self, 
                                        name="Devices")
        self.addWidget("Devices", 
                        self.Devices, 
                        position="left",
                        minSize=(250,800))
        self.Measurement    = DataViewer(self, 
                                        name="Measurement")
        self.addWidget("Measurement",
                        self.Measurement,
                        position="right",
                        relativeTo="Devices",
                        minSize=(500,800))

        # self.controlCamera      = self.Devices.addWidget("Camera Control", 
        #                                                 CameraControlWidget(cam), 
        #                                                 position="top", 
        #                                                 minSize=(250,250))
        # #self.controlCamera.cam_initialize_done.connect(start_the_rest)
        # self.controlAcquisition = self.Devices.addWidget("Acquisition Settings", 
        #                                                 AcquisitionWidget(cam, acquiring=False), 
        #                                                 position="bottom", 
        #                                                 relativeTo="Camera Control", 
        #                                                 minSize=(250,250))
        self.controlAcquisition = self.Devices.addWidget("Camera and Spectrograph Settings", 
                                                        AndorCamSpecWidget(cams, 
                                                                           specs, 
                                                                           acquiring=False), 
                                                        position="top",
                                                        minSize=(250,250))
        self.acquireCamera      = DataAcquirerSpectral(cam.x, 
                                                        self.controlAcquisition.new_data,
                                                        mode)
        self.controlDelaystage  = self.Devices.addWidget("Delay stage", 
                                                        DelayStageWidget(),
                                                        position="bottom", 
                                                        relativeTo="Camera and Spectrograph Settings", 
                                                        minSize=(250,250))
        # self.controlShutter1    = self.Devices.addWidget("Beamshutter", 
        #                                                 BeamshutterWidget(),
        #                                                 position="bottom", 
        #                                                 relativeTo="Delay stage", 
        #                                                 minSize=(250,0))
        # self.controlChopper1    = self.Devices.addWidget("Optical Chopper", 
        #                                                 ChopperControls(),
        #                                                 position="bottom", 
        #                                                 relativeTo="Beamshutter", 
        #                                                 minSize=(250,0))
        # self.controlShutter1.setEnabled(False)
        # self.controlChopper1.setEnabled(False)

        self.logfile        = self.addWidget("Logfile", 
                                                QtGui.QListWidget(self),
                                                position="bottom",
                                                relativeTo="Devices")
        
        self.plotterPOsig = self.Measurement.addWidget("Signal: Probe only", 
                                                        PlotterWidgetSpectral1D( 
                                                            self.acquireCamera.new_data_processed,
                                                            "Signal: Probe only"), 
                                                        position="top", 
                                                        minSize=(250,250))
        self.plotterTAsig = self.Measurement.addWidget("Signal: Ratio", 
                                                        PlotterWidgetSpectral1D(
                                                            self.acquireCamera.new_data_processed,
                                                            "Signal: Ratio"), 
                                                        position="below", 
                                                        relativeTo="Signal: Probe only", 
                                                        minSize=(250,250))
        self.plotterPOrms = self.Measurement.addWidget("RMS: Probe only", 
                                                        PlotterWidgetSpectral1D(
                                                            self.acquireCamera.new_data_processed,
                                                            "RMS: Probe only"), 
                                                        position="bottom", 
                                                        relativeTo="Signal: Ratio", 
                                                        minSize=(250,250))

        # connect signals for plotters to start and stop displaying
        self.controlAcquisition.startDisplay.connect(self.plotterPOsig.startAcq)
        self.controlAcquisition.abortDisplay.connect(self.plotterPOsig.abortAcq)
        self.controlAcquisition.startDisplay.connect(self.plotterTAsig.startAcq)
        self.controlAcquisition.abortDisplay.connect(self.plotterTAsig.abortAcq)
        self.controlAcquisition.startDisplay.connect(self.plotterPOrms.startAcq)
        self.controlAcquisition.abortDisplay.connect(self.plotterPOrms.abortAcq)

        self.joblist      = self.Measurement.addWidget("Job List", 
                                                        JobListWidget(self),
                                                        position="bottom", 
                                                        relativeTo="RMS: Probe only",
                                                        minSize=(300,550))
        #self.jobControl   = self.Measurement.addWidget("Control",
        #     self.configWidget,position="left",Size=(2,2),minSize=(250,250),sizePolicy=(QtGui.QSizePolicy.Fixed,QtGui.QSizePolicy.Fixed))
        
        self.addLogfile()
        
# class LabControl(DataViewer):
#     def __init__(self,parent=None):
#         #os.chdir(os.path.dirname(sys.argv[0]))
#         DataViewer.__init__(self,parent)
#         self.parent=parent
#         self.resize(800,800)
#         self.setWindowTitle("Lab Control")
#         #self.setWindowIcon(QtGui.QIcon('LabView.png'))


#         self.Devices=DataViewer(self,name="Devices")
#         self.Measurement=DataViewer(self,name="Measurement")
#         self.addWidget("Devices",self.Devices)
#         self.addWidget("Measurement",self.Measurement,position="above",relativeTo="Devices",minSize=(250,350))
#         self.Measurement.addWidget("ValveControl",ValveControl(),position="right",minSize=(250,250))
#         self.logfile=self.addWidget("Logfile",QtGui.QListWidget(self),position="bottom",relativeTo="Devices")

#         self.controlDelaystage=self.Devices.addWidget("Delaystage",controlDelaystage.DelayStageWidget(),minSize=(250,250))
#         self.thShutter=self.Devices.addWidget("Thorlabs Beamshutter",ThorlabsBeamshutter.BeamshutterWidget(),position="right",relativeTo="Delaystage",minSize=(250,250))
#         self.piShutter=self.Devices.addWidget("Picard Beamshutter",PicardShutter.PiShutter(),position="bottom",relativeTo="Thorlabs Beamshutter",minSize=(200,150))
#         self.rotationstage=self.Devices.addWidget("Rotation Stage",RotationStage.RotationStageWidget(),position="bottom",relativeTo="Delaystage",minSize=(200,150))
#         self.keithley=self.Devices.addWidget("Keithley",Keithley.KeithleyWidget(),position="left",minSize=(250,250))
#         #self.themis=self.Measurement.addWidget("Themis",ThemisApplication.ThemisApplication(self),position="right",minSize=(250,550))
#         self.themis=ThemisApplication.ThemisApplication(self)
#         self.joblist=self.Measurement.addWidget("Job List",Joblist.JobListWidget(self),position="left",relativeTo="ValveControl",minSize=(300,550))
#         self.addLogfile()



    def closeEvent(self, event):
        quit_msg = "Are you sure you want to exit the program?"
        reply = QtGui.QMessageBox.question(self, 'Message',
                     quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            event.accept()
            #self.controlCamera.close()
            #if hasattr(self.themis,"measurementItem"): self.themis.measurementItem.viewer.close()
        else:
            event.ignore()

    def _del(self):
        pass
        #self.controlShutter1._del()
        #self.rotationstage._del()

    def addLogfile(self):
        self.controlDelaystage.delaystage.throwMessage.connect(self.addToLogfile)
        #self.thShutter.shut.throwMessage.connect(self.addToLogfile)
        self.joblist.throwMessage.connect(self.addToLogfile)
        #self.themis.throwMessage.connect(self.addToLogfile)
        #self.piShutter.throwMessage.connect(self.addToLogfile)
        #self.rotationstage.rotationStage.throwMessage.connect(self.addToLogfile)

    def addToLogfile(self,msg,level=0):
        message=""
        for i in range(level):
            message="  "+message
        message=message+msg
        self.logfile.addItem(message)
        self.logfile.scrollToBottom()



    def excepthook(self,type, value, tb):
        #traceback.print_tb(tb)
        if QCoreApplication.instance() is None:
            app = QtGui.QApplication(sys.argv)
        if type is Exception:
            message = value.args[0]
            detailed = value.args[1]
        else:
            message = "".join(traceback.format_exception_only(type, value) + [" " * 100])
            detailed = "".join(traceback.format_tb(tb))
        self.addToLogfile(message,0)
        self.addToLogfile(detailed,2)
        traceback.print_tb(tb)
        print (message)



if __name__ =='__main__':
    import sys
    import warnings
    import os
    warnings.simplefilter('ignore')

    #sys.argv.append("--model Themis-1000")
    app = QtGui.QApplication(sys.argv)
    os.chdir(os.path.split(sys.argv[0])[0]) #needed for opening from different locations
    #app_icon = QtGui.QIcon("labControl.ico")
    #app.setWindowIcon(app_icon)

    # with SaveSettings.rememberSettings("LabControl.ini") as settings:
    #     labControl=LabControl()
    #     labControl.settings=settings
    #     settings.restoreGui(labControl.controlDelaystage.ui,"DelayStage")
    #     settings.restoreGui(labControl.keithley.ui,"Keithley")
    #     settings.restoreObject(labControl,group="LabControl_Wainwindow")
    #     settings.restoreObject(labControl.area,group="LabControl_Wainwindow")
    #     settings.restoreObject(labControl.Devices.area,group="LabControl_Wainwindow")
    #     settings.restoreObject(labControl.Measurement,group="LabControl_Wainwindow")
    #     settings.restoreObject(labControl.Measurement.area,group="LabControl_Wainwindow")
    #     settings.restoreGui(labControl.joblist,group="LabControl/Joblist/MeasurementDialog")

    #     sys.excepthook = labControl.excepthook
    #     #warnings.simplefilter('ignore', NNW)
    #     labControl.show()
    #     app.exec_()

    # labControl._del()
    # sys.exit()

    #with SaveSettings.rememberSettings("LabControl.ini") as settings:
    diffTASLab=DiffTASLab()
        #labControl.settings=settings
        #settings.restoreGui(labControl.controlDelaystage.ui,"DelayStage")
        #settings.restoreGui(labControl.keithley.ui,"Keithley")
        #settings.restoreObject(labControl,group="LabControl_Wainwindow")
        #settings.restoreObject(labControl.area,group="LabControl_Wainwindow")
        #settings.restoreObject(labControl.Devices.area,group="LabControl_Wainwindow")
        #settings.restoreObject(labControl.Measurement,group="LabControl_Wainwindow")
        #settings.restoreObject(labControl.Measurement.area,group="LabControl_Wainwindow")
        #settings.restoreGui(labControl.joblist,group="LabControl/Joblist/MeasurementDialog")

    sys.excepthook = diffTASLab.excepthook
        #warnings.simplefilter('ignore', NNW)
    diffTASLab.show()
    app.exec_()

    diffTASLab._del()
    sys.exit()


    # init_w.cam_initialize_done.connect(start_the_rest)
    # init_w.cam_shut_down.connect(close_the_rest)

    # def add_device(self, name=None, device=None):
    #     if name in devices:
    #         raise Key


# def main():
#     app = QtGui.QApplication(sys.argv)

#     w = DiffTASLab()
#     w.show()

#     sys.exit(app.exec_())

# if __name__ == "__main__":
#     main()