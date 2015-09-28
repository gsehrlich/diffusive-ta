from __future__ import division
from plotter import Plotter
import numpy as np

class RatioPlotter(Plotter):
    def __init__(self, x, new_probe_only, new_pump_probe):
        # Initialize so that new_probe_only activates the plotting routine
        super(RatioPlotter, self).__init__(x, new_probe_only)
        self.new_pump_probe = new_pump_probe

    def set_pump_probe(self, x_arr, pump_probe):
        self.recent_pump_probe[:] = pump_probe

    def acquire(self, n):
        # Create storage and tallies. Use superclass-created self.storage for
        # probe_only data.
        self.recent_pump_probe = np.zeros(self.x, dtype=np.int32)
        self.pump_probe_storage = np.zeros((n, self.x), dtype=np.int32)
        self.pump_probe_sum = np.zeros(self.x, dtype=np.int64)
        self.probe_only_sum = np.zeros(self.x, dtype=np.int64)

        # Create auxiliary array for calculating ratio
        self.ratio = np.zeros(self.x, dtype=float)

        # Manually connect the signal Plotter doesn't automatically connect
        self.new_pump_probe.connect(self.set_pump_probe)

        super(RatioPlotter, self).acquire(n)

    def send_plot(self, x_arr, probe_only):
        super(RatioPlotter, self).send_plot(x_arr, probe_only)

        # Also copy pump_probe into empty storage
        self.pump_probe_storage[self.i] = self.recent_pump_probe

    def countup_calc(self, x_arr, probe_only):
        # Add arrays into running tallies
        self.pump_probe_sum += self.recent_pump_probe
        self.probe_only_sum += probe_only

        # Calculate and return the ratio. This is true_division
        self.ratio[:] = self.probe_only_sum / self.pump_probe_sum
        return x_arr, self.ratio

    def calc(self, x_arr, probe_only):
        # Take the oldest arrays out of the running tallies
        self.pump_probe_sum -= self.pump_probe_storage[self.i]
        self.probe_only_sum -= self.storage[self.i]

        # Then just do the same as during countup
        return self.countup_calc(x_arr, probe_only)

    def abort(self):
        super(RatioPlotter, self).abort()

        # Manually disconnect the signal Plotter doesn't automatically
        # disocnnect
        self.new_pump_probe.disconnect(self.set_pump_probe)
        del self.recent_pump_probe, self.pump_probe_storage
        del self.pump_probe_sum, self.probe_only_sum
        del self.ratio