Gabriel Ehrlich
gabriel.s.ehrlich@gmail.com
28 September 2015

I'm leaving this project in a half-finished state, so this readme is only going
to contain the minimum information needed to get this thing up and running.
Sorry about that.

To install:
1. Install Python. If you're not sure how, look it up. I recommend the Anaconda
distribution because it comes with a bunch of the scientific Python dependen-
cies that this project relies on.
2. Install the packages. You probably don't have the ones you need yet. To
find out which ones you need:
	a. Try running the program (see below). You will get an ImportError.
	b. Use either pip (command-line package manager installed with Python) or
	conda (better package manager that comes with the Anaconda distribution) to
	install the missing package.
	c. Repeat a. and b. until you have no remaining ImportErrors. Hopefully
	that's the same thing as no remaining errors--the program should start up
	without a hitch.

To run:
1. Open the command prompt. (Hint: click the start menu, click into the search
bar, type "cmd", and then press enter.)
2. Navigate to the folder containing this readme using cd.
3. Type "python cam_full.py" and press enter. Typing "cam_full.py" should work
too.

To switch cameras:
1. Open cam_full.py in your favorite text editor. (Hint: your favorite text
editor is Sublime Text. If you right-click on the file, one of the context
menu options will be "Open with Sublime Text 2".)
2. Line 6 says "cam = newton". To change it from Newton to iDus, replace that
line with "cam = idus". Next time you start it up, it will interface with the
idus instead.