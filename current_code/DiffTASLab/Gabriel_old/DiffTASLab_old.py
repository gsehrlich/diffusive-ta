import sys
import warnings
import traceback
from PyQt4 import QtGui, QtCore, uic
from PyQt4.QtCore import QCoreApplication
from chopper_copy import ChopperControls
from delaystage import DelayStageWidget
from Joblist import JobListWidget
from ThorlabsBeamshutter import BeamshutterWidget
from andor.andorcamera import newton, idus
from MeasurementItem import DataViewer
from cam_control import CameraControlWidget
from acq_control_old import AcquisitionWidget
#from rms import RmsPlotter
#from ratio import RatioPlotter
from plotter_new_old import PlotterWidget, AvgPlotter, RatioPlotter, RmsPlotter


# debug
import time, datetime

global start_w, rms_w, ratio_w, probe_only_w, pump_probe_w
cams = [newton, idus]
#cam  = cams[1]
dflt_x = range(1, 513)

# def init_andor_devices(self):
#     """Initialize all Andor devices (Cameras, Spectrograph). 
#     Do not proceed before initialzition is finished."""
#     for cam in cams:
#         cam.initialize
#         cam.spec.initialize

#     sleep(5)
#     cam_initialize_done.emit()

# def start_the_rest(self):
#     """Start widgets that need the camera to be initialized to work"""

#     self.acq_control = self.Devices.addWidget("Acquisition Settings", 
#                                     AcquisitionWidget(cam, acquiring=False), 
#                                     position="bottom", relativeTo="Camera Control", 
#                                     minSize=(250,250))
#     self.delaystage = self.Devices.addWidget("Delay stage", DelayStageWidget(),
#                                     position="bottom", relativeTo="Camera Control", 
#                                     minSize=(250,250))
#     self.shutter    = self.Devices.addWidget("Beamshutter", BeamshutterWidget(),
#                                     position="bottom", relativeTo="Delay stage", 
#                                     minSize=(250,0))
#     self.chopper    = self.Devices.addWidget("Optical Chopper", ChopperControls(),
#                                     position="bottom", relativeTo="Beamshutter", 
#                                     minSize=(250,0))
#     self.shutter.setEnabled(False)
#     self.chopper.setEnabled(False)
#     self.logfile    = self.addWidget("Logfile", QtGui.QListWidget(self),
#                                     position="bottom",relativeTo="Devices")
    
#     self.plot_raw_sig = self.Measurement.addWidget("Camera Signal", 
#                                     PlotterWidget(AvgPlotter, "Cam Sig", dflt_x, 
#                                         self.acq_control.new_probe_only), 
#                                     position="top", 
#                                     minSize=(250,250))
#     self.plot_tas_sig = self.Measurement.addWidget("TAS Signal", 
#                                     PlotterWidget(RatioPlotter, "TAS Sig", dflt_x, 
#                                         self.acq_control.new_probe_only, 
#                                         self.acq_control.new_pump_probe), 
#                                     position="below", relativeTo="Camera Signal", 
#                                     minSize=(250,250))
#     self.plot_rms_sig = self.Measurement.addWidget("RMS Signal", 
#                                     PlotterWidget(RmsPlotter, "RMS Sig", dflt_x, 
#                                         self.acq_control.new_probe_only), 
#                                     position="bottom", relativeTo="Camera Signal", 
#                                     minSize=(250,250))
#     self.joblist        = self.Measurement.addWidget("Job List", JobListWidget(self),
#                                     position="bottom", relativeTo="RMS Signal",
#                                     minSize=(300,550))
#     # self.joblist        = self.Measurement.addWidget("Job List", JobListWidget(self),
#     #                                 position="bottom",
#     #                                 minSize=(300,550))
   
#     #self.chopper    = self.Devices.addWidget("Optical Chopper", ChopperControls())
#     #self.chopper.setEnabled(False)
#     self.addLogfile()



class DiffTASLab(DataViewer):
    cam_initialize_done = QtCore.pyqtSignal(int)
    spec_initialize = QtCore.pyqtSignal()
    cam_initialize = QtCore.pyqtSignal()
        
    def __init__(self):
        super(DiffTASLab, self).__init__(parent=None)
        self.cam_initialize_done.connect(self.init_UI)
        self.init_andor_devices()
        #self.init_UI()

    def init_andor_devices(self):
        """Initialize all Andor devices (Cameras, Spectrograph). 
        Do not proceed before initialzition is finished."""
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
            print("Init cam: " + actcam.name + "\n")
            actcam.initialize()
            print("Init spec: " + actcam.name + "\n")
            actcam.spec.initialize()

        print("Finished\n")
        self.cam_initialize_done.emit(0)


    def init_UI(self, cam_id):
        cam = cams[cam_id]
        #self.resize(800, 800)
        self.showMaximized()
        #self.devices = {}
        self.Devices        = DataViewer(self,name="Devices")
        self.addWidget("Devices", self.Devices, position="left",
                        minSize=(250,800))
        self.Measurement    = DataViewer(self,name="Measurement")
        self.addWidget("Measurement",self.Measurement,position="right",
                        relativeTo="Devices",minSize=(500,800))
        self.cam_control = self.Devices.addWidget("Camera Control", CameraControlWidget(cam), 
                                        position="top", 
                                        minSize=(250,250))
        #self.cam_control.cam_initialize_done.connect(start_the_rest)
        self.acq_control = self.Devices.addWidget("Acquisition Settings", 
                                        AcquisitionWidget(cam, acquiring=False), 
                                        position="bottom", relativeTo="Camera Control", 
                                        minSize=(250,250))
        # self.camAcquirer = dataAcquirerSpectral(cam.x, self.acq_control.new_data,
        #                                          mode)
        self.delaystage = self.Devices.addWidget("Delay stage", DelayStageWidget(),
                                        position="bottom", relativeTo="Camera Control", 
                                        minSize=(250,250))
        self.shutter    = self.Devices.addWidget("Beamshutter", BeamshutterWidget(),
                                        position="bottom", relativeTo="Delay stage", 
                                        minSize=(250,0))
        self.chopper    = self.Devices.addWidget("Optical Chopper", ChopperControls(),
                                        position="bottom", relativeTo="Beamshutter", 
                                        minSize=(250,0))
        self.shutter.setEnabled(False)
        self.chopper.setEnabled(False)
        self.logfile    = self.addWidget("Logfile", QtGui.QListWidget(self),
                                        position="bottom",relativeTo="Devices")
        
        self.plot_raw_sig = self.Measurement.addWidget("Camera Signal", 
                                        PlotterWidget(AvgPlotter, "Cam Sig", cam.x, 
                                            self.acq_control.new_probe_only), 
                                        position="top", 
                                        minSize=(250,250))
        # self.plot_raw_sig = self.Measurement.addWidget("Signal: Probe only", 
        #                                 PlotterWidget(PlotterWidgetSpectral1D, 
        #                                     self.camAcquirer.new_data_processed,
        #                                     "Signal: Probe only"), 
        #                                 position="top", 
        #                                 minSize=(250,250))
        self.plot_tas_sig = self.Measurement.addWidget("TAS Signal", 
                                        PlotterWidget(RatioPlotter, "TAS Sig", cam.x, 
                                            self.acq_control.new_probe_only, 
                                            self.acq_control.new_pump_probe), 
                                        position="below", relativeTo="Camera Signal", 
                                        minSize=(250,250))
        self.plot_rms_sig = self.Measurement.addWidget("RMS Signal", 
                                        PlotterWidget(RmsPlotter, "RMS Sig", cam.x, 
                                            self.acq_control.new_probe_only), 
                                        position="bottom", relativeTo="Camera Signal", 
                                        minSize=(250,250))
        self.acq_control.startDisplay.connect(self.plot_raw_sig.startAcq)
        self.acq_control.abortDisplay.connect(self.plot_raw_sig.abortAcq)
        self.acq_control.startDisplay.connect(self.plot_tas_sig.startAcq)
        self.acq_control.abortDisplay.connect(self.plot_tas_sig.abortAcq)
        self.acq_control.startDisplay.connect(self.plot_rms_sig.startAcq)
        self.acq_control.abortDisplay.connect(self.plot_rms_sig.abortAcq)

        self.joblist        = self.Measurement.addWidget("Job List", JobListWidget(self),
                                        position="bottom", relativeTo="RMS Signal",
                                        minSize=(300,550))
        # #self.chopper    = self.Devices.addWidget("Optical Chopper", ChopperControls())
        # #self.chopper.setEnabled(False)
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

#         self.delaystage=self.Devices.addWidget("Delaystage",delaystage.DelayStageWidget(),minSize=(250,250))
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
            self.cam_control.close()
            #if hasattr(self.themis,"measurementItem"): self.themis.measurementItem.viewer.close()
        else:
            event.ignore()

    def _del(self):
        self.shutter._del()
        #self.rotationstage._del()

    def addLogfile(self):

        self.delaystage.delaystage.throwMessage.connect(self.addToLogfile)
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
    #     settings.restoreGui(labControl.delaystage.ui,"DelayStage")
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
        #settings.restoreGui(labControl.delaystage.ui,"DelayStage")
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