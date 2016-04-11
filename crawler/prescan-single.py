from time import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json
import string

from afterclickshandlers import LoginPageChecker
from replay import Replayer
from HSTSPreloadList import HSTSPreloadList

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')

inputfile = sys.argv[1]
outputfile = sys.argv[2]

hstspreloadchecker = HSTSPreloadList()

inputdata = json.load(open(sys.argv[1]))

xxx = LoginPageChecker(inputdata["type"], inputdata["url"], hstspreloadchecker)
rep = Replayer(afterClicksHandler=xxx)
rep.replay(inputdata["url"], None, [])
if xxx.hasResult():
    res = xxx.getResult()
    with open(outputfile, 'w') as outfile:
        json.dump(res, outfile)
    sys.exit(0)

sys.exit(1)

