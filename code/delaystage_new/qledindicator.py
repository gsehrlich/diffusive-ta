
from PyQt4.QtGui import QAbstractButton, QPainter, QRadialGradient, QColor, QPen, QBrush
from PyQt4.QtCore import QObject, Qt, QPointF,pyqtProperty

class QLedIndicator(QAbstractButton):
    def __init__(self,parent):
         QAbstractButton.__init__(self)
         self.scaledSize = 1000
         self.setMinimumSize(24,24)
         self.setCheckable(True);
         self._onColor1= QColor(0,255,0)
         self._onColor2= QColor(0,192,0)
         self._offColor1= QColor(0,28,0)
         self._offColor2= QColor(0,128,0)
         self.show()
    def setOnColor1(self,color):
	    self._onColor1=color;
    def getOnColor1(self):
	    return(self.onColor1)
    def setOnColor2(self,color):
	    self._onColor2=color;
    def getOnColor2(self):
	    return(self.onColor2)
    def setOffColor1(self,color):
	    self._offColor1=color;
    def getOffColor1():
	    return(self.offColor1)
    def setOffColor2(self,color):
	    self._offColor2=color;
    def getOffColor2(self):
	    return(self._offColor2)
    onColor1 = pyqtProperty(QColor, fget=getOnColor1, fset=setOnColor1)
    onColor2 = pyqtProperty(QColor, fget=getOnColor2, fset=setOnColor2)
    offColor1 = pyqtProperty(QColor, fget=getOffColor1, fset=setOffColor1)
    offColor2 = pyqtProperty(QColor, fget=getOffColor2, fset=setOffColor2)
	    
    def resizeEvent(self,event):
        self.update()
    def paintEvent(self,event):        
        realSize=min(self.width(),self.height())
       
        painter=QPainter()
        painter.begin(self)
        pen=QPen(Qt.black)
        pen.setWidth(1)
        painter.setPen(Qt.black)
        
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width()/2,self.height()/2)
        painter.scale(float(realSize)/self.scaledSize, float(realSize)/self.scaledSize)
        gradient = QRadialGradient (QPointF(-500,-500), 1500, QPointF(-500,-500));
        gradient.setColorAt(0, QColor(224,224,224));
        gradient.setColorAt(1, QColor(28,28,28));
        painter.setPen(pen);
        painter.setBrush(QBrush(gradient));
        painter.drawEllipse(QPointF(0,0), 500, 500);

        gradient = QRadialGradient (QPointF(500,500), 1500, QPointF(500,500));
        gradient.setColorAt(0, QColor(224,224,224));
        gradient.setColorAt(1, QColor(28,28,28));
        painter.setPen(pen);
        painter.setBrush(QBrush(gradient));
        painter.drawEllipse(QPointF(0,0), 450, 450);
    
        painter.setPen(pen);
        if(self.isChecked()):
            gradient = QRadialGradient (QPointF(-500,-500), 1500, QPointF(-500,-500));
            gradient.setColorAt(0, self._onColor1);
            gradient.setColorAt(1, self._onColor2);
        else:
            gradient = QRadialGradient (QPointF(500,500), 1500, QPointF(500,500));
            gradient.setColorAt(0, self._offColor1);
            gradient.setColorAt(1, self._offColor2);
            
        painter.setBrush(gradient);
        painter.drawEllipse(QPointF(0,0), 400, 400);
        painter.end()


        



