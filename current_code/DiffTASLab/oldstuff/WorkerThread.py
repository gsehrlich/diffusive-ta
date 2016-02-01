from PyQt4.QtCore import QThread
import sys


class WorkerThread(QThread):
     def __init__(self,function=None, *args, **kwargs):
        QThread.__init__(self)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.queue=list()
        self.canDropJobs=False
        self.finished.connect(self.threadFinished)
        self.isFinalized=False

     def __del__(self):
        if self.isFinalized==False:
            self.finalize()

     def finalize(self,timeout=5000):
         self.finalize=True
         self.start=self.blockSart
         self.quit()
         if self.isRunning():
             if timeout==None:
                 self.wait()
             else:
                if not(self.wait(timeout)):
                    raise Exception("Finalizing the WorkerThread timed out, could not terminate thread")


     def blockSart(self):
         pass

     def threadFinished(self):
         if len(self.queue)!=0:
             job=self.queue.pop(0)
             self.function=job["func"]
             self.args = job["args"]
             self.kwargs = job["kwargs"]
             self.start()


     def scheudelFunction(self,function, *args, **kwargs):
         if self.isRunning() :
             self.queue.append({"func":function,"args":args,"kwargs":kwargs})
         else:
             self.function=function
             self.args = args
             self.kwargs = kwargs
             self.start()

     def executeFunction(self,function, *args, **kwargs):
         self.function=function
         self.args = args
         self.kwargs = kwargs
         if not self.isRunning():
             self.start()
         else:
             if not self.canDropJobs:
                raise Exception("Worker Thread was still busy: Could not execute Function")

     def quit(self):
         self.jobs={}
         QThread.quit(self)

     def run(self):
         try:
            self.function(*self.args,**self.kwargs)
         except:
            (type, value, traceback) = sys.exc_info()
            sys.excepthook(type, value, traceback)
         return