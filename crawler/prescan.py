from asyncio.tasks import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json

from PyQt5.Qt import QApplication, QObject
from PyQt5.QtNetwork import QNetworkAccessManager
from PyQt5.QtCore import QSize, QUrl, QByteArray

from core.eventexecutor import EventExecutor, XHRBehavior, EventResult
from core.jaekcore import JaekCore
from utils.requestor import Requestor
from xvfbwrapper import Xvfb
from models.utils import CrawlSpeed
from models.webpage import WebPage

from afterclickshandlers import LoginPageChecker
from replay import Replayer

# perform a quick check on a domain for a login page, without involving the jAEk crawler itself

loginKeywords = ["login", "logon", "signin"]

# check that a given URL is in the correct domain, and has a login keyword
def urlInDomainContainsLoginKeyword(url, domain, keywords):
    urlparts = urlparse(url)
    hostname = urlparts.netloc.split(":")[0]

    # URL is not in the requested domain
    if not hostname.endswith(domain):
        return False

    # remove the domain name from the hostname to avoid false positives
    cleanhostname = hostname[:-len(domain)]
    
    # if a keyword is in the clean hostname, or in the URL path, it's a login page
    return any((kw in cleanhostname or kw in urlparts.path) for kw in keywords)

# https://docs.python.org/3/howto/sorting.html#sortinghowto
def cmp_to_key(mycmp):
    'Convert a cmp= function into a key= function'
    class K(object):
        def __init__(self, obj, *args):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0  
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K

def urlPrioritySort(a, b):
    # - shorter URLs have priority over longer ones
    lendiff = len(a) - len(b)
    if lendiff != 0:
        return lendiff

    # - http has priority over https
    if a.lower().startswith("http://") and not b.lower().startswith("http://"):
        return -1
    if not a.lower().startswith("http://") and b.lower().startswith("http://"):
        return 1

    return 0

def saveData(fn, data):
    logging.info("Found a login page, bailing out. Data:")
    logging.info(pprint.pformat(data))
    json.dump(data, open(fn, "w"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    vdisplay = Xvfb()
    vdisplay.start()

    currentDomain = sys.argv[1]
    topURLpatterns = ["http://{}", "http://www.{}", "https://{}", "https://www.{}"]
    topURLs = [x.format(currentDomain) for x in topURLpatterns]

    #### Step 1: for each toplevel URL of this domain, check if it contains a login page
    topURLresults = []
    for u in topURLs:
        xxx = LoginPageChecker("TOPURL")
        rep = Replayer(afterClicksHandler=xxx)
        rep.replay(u, None, [])
        res = xxx.getResult()

        # if we found a login page, save data and bail out right now
        if "pwfields" in res and len(res["pwfields"]) > 0:
            saveData("out.json", res)
            sys.exit(0)

        topURLresults.append(res)

    #### Step 2: if no login page is found on the toplevel URLs, look for URLs on those page containing
    # words like login, logon, signin, ... in several languages, and check those for a login page

    # gather set of all unique URLs
    containedURLs = list(set(itertools.chain.from_iterable([x["links"] for x in topURLresults])))
    filteredURLs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))

    # sort the list by priority
    sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
    logging.info("Possible Loginpage URLs: ")
    logging.info(pprint.pformat(sortedURLs))

    for u in sortedURLs:
        xxx = LoginPageChecker("LOGINURL")
        rep = Replayer(afterClicksHandler=xxx)
        rep.replay(u, None, [])
        res = xxx.getResult()

        # if we found a login page, save data and bail out right now
        if len(res["pwFields"]) > 0:
            saveData("out.json", res)
            sys.exit(0)

    #### Step 3: if all else fails, launch jAEk to look for a login page

    vdisplay.stop()

