from time import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json
import string

from xvfbwrapper import Xvfb
from models.utils import CrawlSpeed
from utils.user import User
from utils.config import CrawlConfig
from crawler import Crawler
from database.databasemanager import DatabaseManager

from afterclickshandlers import LoginPageChecker
from replay import Replayer

# perform a quick check on a domain for a login page, without involving the jAEk crawler itself

loginKeywords = ["login", "logon", "signin"]

def urlInDomain(url, domain):
    urlparts = urlparse(url)
    hostname = urlparts.netloc.split(":")[0]

    return hostname.endswith(domain)

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
    return any((kw in cleanhostname.lower() or kw in urlparts.path.lower()) for kw in keywords)

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

def saveDataAndExit(fn, data):
    logging.info("Found a login page, bailing out. Data:")
    logging.info(pprint.pformat(data))
    json.dump(data, open(fn, "w"))
    sys.exit(0)

def failDataAndExit(fn, data):
    logging.info("Saving prescan URL and bailing out")
    json.dump(data, open(fn, "w"))
    sys.exit(1)

def isValidDomain(d):
    validchars = string.ascii_lowercase + string.digits + "-."
    return all(c in validchars for c in d)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    vdisplay = Xvfb()
    vdisplay.start()

    currentDomain = sys.argv[1].lower()

    if not isValidDomain(currentDomain):
        logging.info("Invalid domain name {}".format(currentDomain))
        sys.exit(1)

    topURLpatterns = [
        "http://{}", 
        "http://login.{}", 
        "http://{}/login", 
        "http://www.{}", 
        "http://www.{}/login", 
        "https://{}", 
        "https://login.{}", 
        "https://{}/login", 
        "https://www.{}", 
        "https://www.{}/login", 
    ]
    topURLs = [x.format(currentDomain) for x in topURLpatterns]

    firstWorkingURL = None

    #### Step 1: for each toplevel URL of this domain, check if it contains a login page
    topURLresults = []
    counter = 0
    for u in topURLs:
        logging.debug("Starting prescan of top url {}".format(counter))
        xxx = LoginPageChecker("TOPURL{} {}".format(counter, topURLpatterns[counter]), u)
        rep = Replayer(afterClicksHandler=xxx)
        errorcode, html = rep.replay(u, None, [])

        if xxx.hasResult():
            if firstWorkingURL == None:
                firstWorkingURL = u
            logging.debug("Inspecting results for prescan of top url {}: {}".format(counter, u))
            res = xxx.getResult()

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                saveDataAndExit("out.json", res)

            topURLresults.append(res)
            logging.debug("Done with prescan of top url {}: {}".format(counter, u))
        else:
            logging.debug("Failed prescan of top url {}: {}".format(counter, u))
        xxx = None
        rep = None
        counter += 1

    #### Step 2: if no login page is found on the toplevel URLs, look for URLs on those page containing
    # words like login, logon, signin, ... in several languages, and check those for a login page

    # gather set of all unique URLs
    containedURLs = list(set(itertools.chain.from_iterable([x["links"] for x in topURLresults])))
    logging.info("Discovered these URLs: ")
    logging.info(pprint.pformat(containedURLs))
    filteredURLs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))

    # sort the list by priority
    sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
    logging.info("Possible Loginpage URLs: ")
    logging.info(pprint.pformat(sortedURLs))

    for u in sortedURLs:
        logging.debug("Starting prescan of possible login url {}".format(u))
        xxx = LoginPageChecker("LOGINURL", u)
        rep = Replayer(afterClicksHandler=xxx)
        rep.replay(u, None, [])
        if xxx.hasResult():
            logging.debug("Inspecting results for prescan of possible login url {}".format(u))
            res = xxx.getResult()

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                saveDataAndExit("out.json", res)

            logging.debug("Done with prescan of possible login url {}".format(u))
        else:
            logging.debug("Failed prescan of possible login url {}".format(u))
        xxx = None
        rep = None
    failDataAndExit("out.json", {"crawlurl": firstWorkingURL})
    logging.debug("prescan.py is done")
    vdisplay.stop()

