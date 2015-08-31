import time
import multiprocessing as mp

class MyProcess(mp.Process):
    def run(self):
        while True:
            time.sleep(1)

if __name__ == '__main__':
    p = MyProcess()
    p.daemon = True
    p.start()

    w = raw_input("? ")

    raise NameError