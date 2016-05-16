from time import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json
import string
import os.path

from models.utils import CrawlSpeed
from utils.user import User
from utils.config import CrawlConfig
from crawler import Crawler
from database.databasemanager import DatabaseManager

from afterclickshandlers import LoginPageChecker
from replay import Replayer
from HSTSPreloadList import HSTSPreloadList


def loadData(fn):
    indata = json.load(open(fn))
    url = indata["origurl"]
    initclick = Clickable.fromDict(indata["element_to_click"]) if indata["element_to_click"] != None else None
    preclicks = [Clickable(None,None,None).fromDict(x) if x != None else None for x in indata["pre_clicks"]]
    return url, initclick, preclicks


def cleanupRedirectPageResources(data):
   try:
       for (url,rec) in data["redirectPageResources"].items():
           for (t, rec2) in rec.items():
               if type(rec2) == dict:
                   for (url2, rec3) in rec2.items():
                       del rec3["redirectchain"]
       del data["links"]
   except:
       pass
   return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')

    if len(sys.argv) == 5:
        attackermodel = sys.argv[1]
        domain = sys.argv[2]
        inputfile = sys.argv[3]
        port = int(sys.argv[4])
        url, initclick, preclicks = loadData(inputfile)

    else:
        attackermodel = "god"
        inputfile = "FIXME"
        port = 8080
        url, initclick, preclicks = sys.argv[1], None, []
        urlparts = urlparse(url)
        domain = urlparts.hostname

    hstspreloadchecker = HSTSPreloadList()

    xxx = LoginPageChecker("TEST", url, hstspreloadchecker, domain = domain)
    rep = Replayer(proxy="localhost", port=port, afterClicksHandler=xxx)
    errorcode, html = rep.replay(url, initclick, preclicks, timeout=60, delay=15)


    if xxx.hasResult():
        res = xxx.getResult()
        res2 = cleanupRedirectPageResources(res)
        logging.info(pprint.pformat(res2))
        json.dump(res, open("visitor-output-{}.json".format(attackermodel), "w"))
    else:
        logging.info("No result found :(")



#TODO:
#       this script should be launched as the browser during an attack
#       input: a replay record + the attacker model being used right now
#       output:
#           - parsed info on which attacks succeeded
#           - CSS tainted?
#           - target of form
#           - BAMC/UIR/SRI


# parse input structure to get url, domain, clicks and attacker model(?)
# listen to alerts and gather the alerted data








