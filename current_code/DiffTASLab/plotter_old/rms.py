from __future__ import division
import numpy as np
from contextlib import contextmanager
from plotter import Plotter, PlotterWidget
import atexit

class RmsPlotter(Plotter):
    def acquire(self, n):
        # Set up tallies
        self.sum = np.zeros(self.x, dtype=np.int64)
        self.sum_sq = np.zeros(self.x, dtype=np.int64)

        # Pre-allocate auxiliary arrays for calculation
        self.avg = np.zeros(self.x, dtype=float)
        self.rms = np.zeros(self.x, dtype=float)
        self.percent_err = np.zeros(self.x, dtype=float)

        # Let the superclass take care of the rest
        super(RmsPlotter, self).acquire(n)

    def countup_calc(self, x_arr, y_arr):
        # Add y_arr into running tallies
        self.sum += y_arr
        self.sum_sq += y_arr**2

        # Calculate: rms = sqrt(<x^2> - <x>^2). This is true_divide
        self.avg[:] = self.sum / self.start_countup
        self.rms[:] = np.sqrt(self.sum_sq/self.start_countup - self.avg**2)
        self.percent_err[:] = self.rms / self.avg
        return x_arr, self.percent_err

    def calc(self, x_arr, y_arr):
        # Take the oldest y_arr out of the running tallies
        self.sum -= self.storage[self.i]
        self.sum_sq -= self.storage[self.i]**2

        # Then just do the same as during countup
        return self.countup_calc(x_arr, y_arr)

    def abort(self):
        super(RmsPlotter, self).abort()
        del self.sum_sq, self.rms, self.percent_err