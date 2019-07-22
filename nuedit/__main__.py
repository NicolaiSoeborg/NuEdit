import logging
import sys
from multiprocessing import freeze_support
# from gevent import monkey; monkey.patch_socket()

from .editor import editor

logging.basicConfig(
    level=logging.DEBUG,
    filename='/tmp/nuedit.log',
    filemode='w',
    format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s')


if __name__ == '__main__':
    freeze_support()  # py2exe support, etc
    editor(sys.argv[1:])
