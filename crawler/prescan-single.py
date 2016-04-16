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

if len(sys.argv) == 3:
    inputfile = sys.argv[1]
    outputfile = sys.argv[2]
    inputdata = json.load(open(inputfile))
else:
    inputdata = {
        "url": sys.argv[1],
        "type": "TEST"
    }
    outputfile = "output.json"


hstspreloadchecker = HSTSPreloadList()

xxx = LoginPageChecker(inputdata["type"], inputdata["url"], hstspreloadchecker, domain = inputdata["domain"])
rep = Replayer(afterClicksHandler=xxx)
rep.replay(inputdata["url"], None, [])
if xxx.hasResult():
    res = xxx.getResult()
    with open(outputfile, 'w') as outfile:
        json.dump(res, outfile)
    sys.exit(0)

sys.exit(1)

