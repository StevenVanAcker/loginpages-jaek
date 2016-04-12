from time import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json
import string
import subprocess, os, tempfile

from models.utils import CrawlSpeed
from utils.user import User
from utils.config import CrawlConfig
from crawler import Crawler
from database.databasemanager import DatabaseManager

from afterclickshandlers import LoginPageChecker
from replay import Replayer
from HSTSPreloadList import HSTSPreloadList

# perform a check on a domain for a login page, without involving the jAEk crawler itself

loginKeywords = [
        "login",        "logon",        "signin",       "account",      # English
"wechall",
        #"login",       "logon",        "signin",       "account",      # Russian
        "anmeldung",    "einloggen",    "anmelden",     "konto",        # German
        #"login",       "logon",        "signin",       "account",      # Japanese
        #"login",       "logon",        "signin",       "account",      # Spanish
        #"login",       "logon",        "signin",       "account",      # French
        #"login",       "logon",        "signin",       "account",      # Portuguese
        #"login",       "logon",        "signin",       "account",      # Italian
        #"login",       "logon",        "signin",       "account",      # Chinese
        #"login",       "logon",        "signin",       "account",      # Polish
        #"login",       "logon",        "signin",       "account",      # Turkish
]
#FIXME: add different languages
BINGSIZE = 20

def urlInDomain(url, domain): #{{{
    urlparts = urlparse(url)
    hostname = urlparts.netloc.split(":")[0]

    return hostname.endswith(domain)
#}}}
def urlInDomainContainsLoginKeyword(urlrec, domain, keywords): #{{{
    # check that a given URL is in the correct domain, and the URL or link text has a login keyword
    url, txt = urlrec
    urlparts = urlparse(url)
    hostname = urlparts.netloc.split(":")[0]

    # URL is not in the requested domain
    if not hostname.endswith(domain):
        return False

    # remove the domain name from the hostname to avoid false positives
    cleanhostname = hostname[:-len(domain)]
    
    # if a keyword is in the clean hostname, or in the URL path, it's a login page
    url_is_login = any((kw in cleanhostname.lower() or kw in urlparts.path.lower()) for kw in keywords)
    flattxt = "".join(txt.lower().split(" "))
    txt_is_login = any(kw in flattxt for kw in keywords)
    return url_is_login or txt_is_login
#}}}
def cmp_to_key(mycmp): #{{{
    # https://docs.python.org/3/howto/sorting.html#sortinghowto
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
#}}}
def urlPrioritySort(a, b): #{{{
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
#}}}
def saveDataAndExit(fn, data): #{{{
    logging.info("Found a login page, bailing out. Data:")
    logging.info(pprint.pformat(data))
    json.dump(data, open(fn, "w"))
    sys.exit(0)
#}}}
def failDataAndExit(fn, data): #{{{
    logging.info("Saving prescan URL and bailing out")
    json.dump(data, open(fn, "w"))
    sys.exit(1)
#}}}
def isValidDomain(d): #{{{
    validchars = string.ascii_lowercase + string.digits + "-."
    return all(c in validchars for c in d)
#}}}
def visitPage(t, u): #{{{
    d = os.path.dirname(os.path.realpath(__file__))
    tmpinfd = tempfile.NamedTemporaryFile(delete=False)  
    tmpoutfd = tempfile.NamedTemporaryFile(delete=False)  
    tmpin = tmpinfd.name
    tmpout = tmpoutfd.name
    tmpinfd.close()
    tmpoutfd.close()
    indata = { "url": u, "type": t }
    json.dump(indata, open(tmpin, 'w'))
    json.dump(None, open(tmpout, 'w'))

    child = subprocess.Popen([sys.executable, d + "/prescan-single.py", tmpin, tmpout])
    child.communicate()
    rc = child.returncode

    data = None
    if rc == 0:
        try:
            data = json.load(open(tmpout))
        except:
            pass

    if data == None:
        logging.debug("*********************************************")
        logging.debug("********** CRASH DETECTED (AGAIN) ***********")
        logging.debug("*********************************************")

    os.unlink(tmpin)
    os.unlink(tmpout)

    return data
#}}}
def bingdataFor(domain): #{{{
    fn = "/usr/src/bingdata/{}.json".format(domain)
    try:
        return [k for (k,v) in json.load(open(fn)).items()][:BINGSIZE]
    except:
        return []
#}}}

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    currentDomain = sys.argv[1].lower()

    if not isValidDomain(currentDomain):
        logging.info("Invalid domain name {}".format(currentDomain))
        sys.exit(1)


    topURLpatterns = [
        "http://{}", 
        "https://{}", 
        "http://www.{}", 
        "https://www.{}", 
    ]
    # topURLpatterns += ["https://www.{}/?xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"+str(i) for i in range(10)]

    topURLs = [x.format(currentDomain) for x in topURLpatterns]
    bingURLs = bingdataFor(currentDomain)
    try:
        bingURLs = json.load(open("/data/stuff.json")) # FIXME
    except:
        pass
    hstspreloadchecker = HSTSPreloadList()

    firstWorkingURL = None
    visitedURLs = set()

    #### Step 1: for each toplevel URL of this domain, check if it contains a login page {{{
    topURLresults = []
    counter = 0
    for u in topURLs:
        if u in visitedURLs:
            logging.debug("Skipping already visited top url {}".format(u))
            continue
        visitedURLs.add(u)

        logging.debug("Starting prescan of top url {}".format(counter))
        res = visitPage("TOPURL{} {}".format(counter, topURLpatterns[counter]), u)

        if res:
            if firstWorkingURL == None:
                firstWorkingURL = u
            logging.debug("Inspecting results for prescan of top url {}: {}".format(counter, u))

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                visitedURLs.add(res["url"])
                saveDataAndExit("output.json", res)

            topURLresults.append(res)
            logging.debug("Done with prescan of top url {}: {}".format(counter, u))
        else:
            logging.debug("Failed prescan of top url {}: {}".format(counter, u))
        counter += 1
    #}}}
    #### Step 2: if no login page is found on the toplevel URLs, look for URLs on those page containing {{{
    # words like login, logon, signin, ... in several languages, and check those for a login page

    # gather set of all unique URLs
    containedURLs = itertools.chain.from_iterable([x["links"] for x in topURLresults])
    filteredURLTXTs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))
    filteredURLs = list(set([u for (u,t) in filteredURLTXTs]))

    # sort the list by priority
    sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
    logging.info("Possible Loginpage URLs: ")
    logging.info(pprint.pformat(sortedURLs))

    for u in sortedURLs:
        if u in visitedURLs:
            logging.debug("Skipping already visited possible login url {}".format(u))
            continue
        visitedURLs.add(u)

        logging.debug("Starting prescan of possible login url {}".format(u))
        res = visitPage("LOGINURL", u)
        if res:
            logging.debug("Inspecting results for prescan of possible login url {}".format(u))

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                visitedURLs.add(res["url"])
                saveDataAndExit("output.json", res)

            logging.debug("Done with prescan of possible login url {}".format(u))
        else:
            logging.debug("Failed prescan of possible login url {}".format(u))
    #}}}
    #### Step 3: visit top Bing pages for this domain, check for login page {{{
    # remove already checked pages from the bing URL list...
    bingURLresults = []
    counter = 0
    for u in bingURLs:
        if u in visitedURLs:
            logging.debug("Skipping already visited bing url {}".format(u))
            continue
        visitedURLs.add(u)

        logging.debug("Starting prescan of bing url {}".format(counter))
        res = visitPage("BINGURL{} {}".format(counter, bingURLpatterns[counter]), u)

        if res:
            if firstWorkingURL == None:
                firstWorkingURL = u
            logging.debug("Inspecting results for prescan of bing url {}: {}".format(counter, u))

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                visitedURLs.add(res["url"])
                saveDataAndExit("output.json", res)

            bingURLresults.append(res)
            logging.debug("Done with prescan of bing url {}: {}".format(counter, u))
        else:
            logging.debug("Failed prescan of bing url {}: {}".format(counter, u))
        counter += 1
    #}}}
    #### Step 4: visit any linked pages from top Bing pages with login keywords in them {{{
    # gather set of all unique URLs
    containedURLs = itertools.chain.from_iterable([x["links"] for x in bingURLresults])
    filteredURLTXTs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))
    filteredURLs = list(set([u for (u,t) in filteredURLTXTs]))

    # sort the list by priority
    sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
    logging.info("Possible Loginpage URLs: ")
    logging.info(pprint.pformat(sortedURLs))

    for u in sortedURLs:
        if u in visitedURLs:
            logging.debug("Skipping already visited possible bing login url {}".format(u))
            continue
        visitedURLs.add(u)
        logging.debug("Starting prescan of possible bing login url {}".format(u))
        res = visitPage("BINGLOGINURL", u)
        if res:
            logging.debug("Inspecting results for prescan of possible bing login url {}".format(u))

            # if we found a login page, save data and bail out right now
            if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
                visitedURLs.add(res["url"])
                saveDataAndExit("output.json", res)

            logging.debug("Done with prescan of possible bing login url {}".format(u))
        else:
            logging.debug("Failed prescan of possible bing login url {}".format(u))
    #}}}

    failDataAndExit("output.json", {"crawlurl": firstWorkingURL})
    logging.debug("prescan.py is done")

