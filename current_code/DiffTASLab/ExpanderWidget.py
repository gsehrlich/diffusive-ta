from PyQt4.QtCore import *
from PyQt4.QtGui import *

class ExpanderWidget(QWidget):
    expanderChanged=pyqtSignal(bool,name="expanderChanged")
    currentIndexChanged=pyqtSignal(int,name="currentIndexChanged")
    def __init__(self,Widget=None):
        QWidget.__init__(self)
        self.expanded=True
        self.button =QPushButton()
        self.button.setObjectName("__qt__passive_button")
        self.button.setText("Expander")
        self.button.setIcon(QIcon("Bilder/arrow-expanded.png"))
        self.button.setFlat(True)
        self.button.setStyleSheet("text-align: left; font-weight: bold; border: none;")

        self.button.clicked.connect(self.buttonPressed)

        self.stackWidget =QStackedWidget()

        self.layout =QVBoxLayout()
        #self.layout.setContentsMargins(0,0,0,0)


        if not Widget==None:
            hbox=QHBoxLayout()
            hbox.addWidget(self.button,0, Qt.AlignLeft)
            hbox.addWidget(Widget)
            self.layout.addLayout(hbox)
        else:
            self.layout.addWidget(self.button, 0, Qt.AlignTop)
        self.layout.addWidget(self.stackWidget)
        self.setLayout(self.layout)


    def buttonPressed(self):
        if self.expanded:
            self.expanded = False
            self.button.setIcon(QIcon("Bilder/arrow.png"))

            size = self.layout.sizeHint()
            width = size.width()
            height = size.height()
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            self.stackWidget.hide()
            self.resize(width, 20)
            self.updateGeometry()

        else:
            self.expanded = True
            self.button.setIcon(QIcon("Bilder/arrow-expanded.png"))
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.stackWidget.show()
            self.updateGeometry()
        self.expanderChanged.emit(self.expanded)

    def sizeHint(self):
        return QSize(200, 20)

    def addWidget(self,Widget):
        self.insertWidget(self.count(), Widget)

    def removeWidget(self,index):
        self.stackWidget.removeWidget(self.widget(index))

    def count(self):
        return self.stackWidget.count()

    def currentIndex(self):
        return self.stackWidget.currentIndex()

    def addLayout(self,layout):
        widget=QWidget()
        #widget.setContentsMargins(0,0,0,0)
        widget.setLayout(layout)
        self.addWidget(widget)

    def insertWidget(self,index, page):
        page.setParent(self.stackWidget)
        self.stackWidget.insertWidget(index, page)

    def setCurrentIndex(self,int,index):
        if not index == self.stackWidget.currentIndex():
            self.stackWidget.setCurrentIndex(index)
            self.currentIndexChanged.emit(index)

    def widget(self,index):
        return self.stackWidget.widget(index)

    def setText(self, newTitle):
        self.button.setText(newTitle)

    def expanderTitle(self):
       return self.button.text()


    def setExpanded(self,flag):
        if not flag == self.expanded:
            self.buttonPressed()
        else:
            self.expanded = flag

    def isExpanded(self):
        return self.expanded
