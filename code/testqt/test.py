# from http://pythonforengineers.com/your-first-gui-app-with-python-and-pyqt/

import sys
from PyQt4 import QtCore, QtGui, uic
import os.path

ui_filename = "mainwindow.ui"

# Parse the Designer .ui file
Ui_MainWindow, QtBaseClass = uic.loadUiType(ui_filename)

class TaxCalculator(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        # connect events to methods
        self.calc_button.clicked.connect(self.calculate_tax)
        self.tax_slider.valueChanged.connect(self.update_tax_label)

    def keyPressEvent(self, event):
        QtGui.QMainWindow.keyPressEvent(self, event)
        
        if event.key() == QtCore.Qt.Key_Enter:
            calculate_tax()

    def calculate_tax(self):
        # when the calc button is clicked
        price_cents = get_price_cents(self.price_editor.text())
        tax = self.tax_slider.value() # per ten thousand, not percent
        total_price_cents = int(price_cents + (tax*1e-4 * price_cents))
        answer_string = "The total price with tax is: $%d.%02d"
        self.tax_result_browser.setText(answer_string %
            (total_price_cents/100, total_price_cents % 100))

    def update_tax_label(self):
        # when the slider value changes (incl. mid-drag)
        val = self.tax_slider.value() # per ten thousand; integer
        s = "%d.%02d" % (val/100, val%100) + '%'
        self.tax_value.setText(s)
        self.calculate_tax()

def get_price_cents(price_Qstring, European=True):
    decimal, counter = '.', ','
    if European: decimal, counter = counter, decimal

    dollars, cents = str(price_Qstring).split(decimal)
    return int(' '.join(dollars.split(counter)) + cents[:2])

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = TaxCalculator()
    window.show()
    sys.exit(app.exec_())