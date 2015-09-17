import types

class GuiProperty(property):
    def __init__(self, *args):
        super(GuiProperty, self).__init__(*args)

        def update(fn):
            self._update = fn

        self.update = update
