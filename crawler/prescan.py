from time import sleep
import logging
import sys
import pprint
from urllib.parse import urlparse
import itertools
import json
import string
import subprocess, os, tempfile, shutil

from models.utils import CrawlSpeed
from utils.user import User
from utils.config import CrawlConfig
from crawler import Crawler
from database.databasemanager import DatabaseManager

from replay import Replayer
from HSTSPreloadList import HSTSPreloadList

# perform a check on a domain for a login page, without involving the jAEk crawler itself

loginKeywords = [
"account", "identification", "identify", "login", "logon", "password", "signin", "username",                    # English
"akkaunt", "avtorizatsiya", "avtorizirovatsya", "parol", "vhod", "voidite", "voiti",                            # Russian
"anmelden", "anmeldung", "einloggen", "konto",                                                                  # German
"hairu", "passwado",                                                                                            # Japanese
"accede", "acceso", "contrasena", "cuenta", "entra", "ingresa", "ingreso", "nombredeusuario", "usuario",        # Spanish
"acces", "compte", "connecter", "connexion", "email", "espaceperso", "identifiant", "identifier", "mapage",
"meconnecter", "midentifier", "moncompte", "seconnecter", "sidentifier",                                        # French
"assinarem", "conta", "identificacao", "identificar", "nomedeusuario", "senha",                                 # Portuguese
"accedi", "accesso", "chiavedaccesso", "connetti", "datidaccesso", "fammientrare", "frasedaccesso", 
"nomeutente", "parolachiave", "registra", "userid", "utente",                                                   # Italian
"denglu", "jianding", "mima", "qiandao", "shibie", "yonhuming", "zhanghu",                                      # Chinese
"adresemail", "akceptujeregulamin", "aktywacja", "aktywuj", "bezpieczenstwo", "dalej", "dostep", "haslo",
"identyfikator", "logowanie", "nazwauzytkownika", "niepamietamhasla", "połacz", "politykaprywatnosci",
"przegladarka", "przypomnijhaslo", "regulamin", "serwis", "utworzkonto", "uzytkownik", "wejdz", "weryfikacja", 
"zaakceptujregulamin", "zaloguj", "zarejestruj",                                                                # Polish
"belirlemek", "hesap", "kimlik", "kullaniciadi", "oturum", "parola",                                            # Turkish
]

BINGSIZE = 20
CRAWLERTIMEOUT = 1800
skipStep1 = True and False
skipStep2 = True and False
skipStep3 = True and False
skipStep4 = True and False
skipStep5 = True and False

def urlInDomain(url, domain): #{{{
    urlparts = urlparse(url)
    hostname = "."+urlparts.netloc.split(":")[0]

    return hostname.endswith("."+domain)
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
    if "success" not in data:
        data["success"] = False
    if data["success"]:
        logging.info("Found a login page at {} --> bailing out.".format(data["url"]))
    else:
        logging.info("Failed to find a login page --> bailing out.")
    #logging.info(pprint.pformat(data))
    json.dump(data, open(fn, "w"))
    sys.exit(0)
#}}}
def isValidDomain(d): #{{{
    validchars = string.ascii_lowercase + string.digits + "-."
    return all(c in validchars for c in d)
#}}}
def visitPage(t, u, dom, retry = 1): #{{{
    thisdir = os.path.dirname(os.path.realpath(__file__))
    tmpinfd = tempfile.NamedTemporaryFile(delete=False)  
    tmpoutfd = tempfile.NamedTemporaryFile(delete=False)  
    tmpin = tmpinfd.name
    tmpout = tmpoutfd.name
    tmpinfd.close()
    tmpoutfd.close()
    indata = { "url": u, "type": t, "domain": dom}
    json.dump(indata, open(tmpin, 'w'))
    json.dump(None, open(tmpout, 'w'))

    child = subprocess.Popen([sys.executable, thisdir + "/prescan-single.py", tmpin, tmpout])
    child.communicate()
    rc = child.returncode

    data = None
    if rc == 0:
        try:
            data = json.load(open(tmpout))
        except:
            pass

    os.unlink(tmpin)
    os.unlink(tmpout)

    logging.debug("****** RETURN CODE == {} ******".format(rc))

    if data == None and rc != 0 and rc != 1:
        if retry > 0:
            logging.debug("*********************************************")
            logging.debug("****** CRASH DETECTED (TRYING {} MORE) ******".format(retry))
            logging.debug("*********************************************")
            data = visitPage(t, u, dom, retry - 1)
        else:
            logging.debug("*********************************************")
            logging.debug("***** CRASH DETECTED (NOT TRYING AGAIN) *****")
            logging.debug("*********************************************")

    return data
#}}}
def bingdataFor(domain): #{{{
    fn = "/usr/src/bingdata/{}.json".format(domain)
    try:
        return [k for (k,v) in json.load(open(fn)).items()][:BINGSIZE]
    except:
        return []
#}}}

def handleValidResult(res): #{{{
    if "url" in res and "pwfields" in res and urlInDomain(res["url"], currentDomain) and len(res["pwfields"]) > 0:
        saveDataAndExit("output.json", res)
        return True
    else:
        # if we have no valid result, then any screenshots were mistakingly generated. remove them
        if os.path.exists("screenshot.png"):
            os.unlink("screenshot.png")
        return False
#}}}

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')

    if len(sys.argv) > 1:
        currentDomain = sys.argv[1].lower()
    else:
        indata = json.load(open("input.json"))
        currentDomain = indata["domain"].lower()

    with open("output.json", "w") as fp:
        json.dump({"success": False, "domain": currentDomain}, fp)

    if not isValidDomain(currentDomain):
        logging.info("Invalid domain name {}".format(currentDomain))
        sys.exit(1)

    logging.debug("#### PRESCAN OF DOMAIN {}".format(currentDomain))

    topURLpatterns = [
        "http://{}", 
        "https://{}", 
        "http://www.{}", 
        "https://www.{}", 
    ]

    topURLs = [x.format(currentDomain) for x in topURLpatterns]
    bingURLs = bingdataFor(currentDomain)
    hstspreloadchecker = HSTSPreloadList()

    firstWorkingURL = None
    visitedURLs = set()

    #### Step 1: for each toplevel URL of this domain, check if it contains a login page {{{
    topURLresults = []
    if not skipStep1:
        logging.debug("###########################")
        logging.debug("########## STEP 1 #########")
        logging.debug("###########################")
        counter = 0
        for u in topURLs:
            counter += 1
            if u in visitedURLs:
                logging.debug("### Skipping already visited top url {}".format(u))
                continue
            visitedURLs.add(u)

            logging.debug("### Starting prescan of top url {}/{}".format(counter, len(topURLs)))
            res = visitPage("TOPURL{} {}".format(counter, topURLpatterns[counter-1]), u, currentDomain)

            if res:
                if firstWorkingURL == None:
                    firstWorkingURL = u
                logging.debug("Inspecting results for prescan of top url {}: {}".format(counter, u))

                # if we found a login page, save data and bail out right now
                handleValidResult(res)
                topURLresults.append(res)
                logging.debug("### Done with prescan of top url {}: {}".format(counter, u))
            else:
                logging.debug("### Failed prescan of top url {}: {}".format(counter, u))
    else:
        firstWorkingURL = "http://{}".format(currentDomain)
    #}}}
    #### Step 2: if no login page is found on the toplevel URLs, look for URLs on those page containing {{{
    if not skipStep2:
        logging.debug("###########################")
        logging.debug("########## STEP 2 #########")
        logging.debug("###########################")
        # words like login, logon, signin, ... in several languages, and check those for a login page

        # gather set of all unique URLs
        containedURLs = itertools.chain.from_iterable([x["links"] for x in topURLresults])
        filteredURLTXTs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))
        filteredURLs = list(set([u for (u,t) in filteredURLTXTs]))

        # sort the list by priority
        sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
        logging.info("Possible Loginpage URLs: ")
        logging.info(pprint.pformat(sortedURLs))

        counter = 0
        for u in sortedURLs:
            counter += 1
            if u in visitedURLs:
                logging.debug("### Skipping already visited possible login url {}".format(u))
                continue
            visitedURLs.add(u)

            logging.debug("### Starting prescan of possible login url ({}/{}) {}".format(counter, len(sortedURLs), u))
            res = visitPage("LOGINURL{}".format(counter), u, currentDomain)
            if res:
                logging.debug("Inspecting results for prescan of possible login url {}".format(u))

                # if we found a login page, save data and bail out right now
                handleValidResult(res)
                logging.debug("### Done with prescan of possible login url {}".format(u))
            else:
                logging.debug("### Failed prescan of possible login url {}".format(u))
    #}}}
    #### Step 3: visit top Bing pages for this domain, check for login page {{{
    bingURLresults = []
    if not skipStep3:
        logging.debug("###########################")
        logging.debug("########## STEP 3 #########")
        logging.debug("###########################")
        # remove already checked pages from the bing URL list...
        counter = 0
        for u in bingURLs:
            counter += 1
            if u in visitedURLs:
                logging.debug("### Skipping already visited bing url {}".format(u))
                continue
            visitedURLs.add(u)

            logging.debug("### Starting prescan of bing url {}/{}".format(counter, len(bingURLs)))
            res = visitPage("BINGURL{}".format(counter), u, currentDomain)

            if res:
                if firstWorkingURL == None:
                    firstWorkingURL = u
                logging.debug("Inspecting results for prescan of bing url {}: {}".format(counter, u))

                # if we found a login page, save data and bail out right now
                handleValidResult(res)
                bingURLresults.append(res)
                logging.debug("### Done with prescan of bing url {}: {}".format(counter, u))
            else:
                logging.debug("### Failed prescan of bing url {}: {}".format(counter, u))
    #}}}
    #### Step 4: visit any linked pages from top Bing pages with login keywords in them {{{
    if not skipStep4:
        logging.debug("###########################")
        logging.debug("########## STEP 4 #########")
        logging.debug("###########################")
        # gather set of all unique URLs
        containedURLs = itertools.chain.from_iterable([x["links"] for x in bingURLresults])
        filteredURLTXTs = list(filter(lambda x: urlInDomainContainsLoginKeyword(x, currentDomain, loginKeywords), containedURLs))
        filteredURLs = list(set([u for (u,t) in filteredURLTXTs]))

        # sort the list by priority
        sortedURLs = sorted(filteredURLs, key=cmp_to_key(urlPrioritySort))
        logging.info("Possible Loginpage URLs: ")
        logging.info(pprint.pformat(sortedURLs))

        counter = 0
        for u in sortedURLs:
            counter += 1
            if u in visitedURLs:
                logging.debug("### Skipping already visited possible bing login url {}".format(u))
                continue
            visitedURLs.add(u)
            logging.debug("### Starting prescan of possible bing login url ({}/{}) {}".format(counter, len(sortedURLs), u))
            res = visitPage("BINGLOGINURL{}".format(counter), u, currentDomain)
            if res:
                logging.debug("Inspecting results for prescan of possible bing login url {}".format(u))

                # if we found a login page, save data and bail out right now
                handleValidResult(res)
                logging.debug("### Done with prescan of possible bing login url {}".format(u))
            else:
                logging.debug("### Failed prescan of possible bing login url {}".format(u))
    #}}}
    #### Step 5: invoke jAEk {{{
    if not skipStep5:
        logging.debug("###########################")
        logging.debug("########## STEP 5 #########")
        logging.debug("###########################")

        logging.debug("### Starting jAEk crawler on {}".format(firstWorkingURL))
        d = os.path.dirname(os.path.realpath(__file__))
        tmpinfd = tempfile.NamedTemporaryFile(delete=False)  
        tmpin = tmpinfd.name
        tmpinfd.close()
        indata = { "url": firstWorkingURL, "domain": currentDomain }
        json.dump(indata, open(tmpin, 'w'))

        if os.path.exists("output-jaek.json"):
            os.unlink("output-jaek.json")
        if os.path.exists("similarities"):
            shutil.rmtree("similarities")
        os.mkdir("similarities")

        child = subprocess.Popen(["timeout", "--signal=9", "{}".format(CRAWLERTIMEOUT), sys.executable, d + "/main.py", tmpin])
        child.communicate()
        rc = child.returncode
        if rc != 0:
            logging.debug("#### jAEk failed with code {}".format(rc))
        else:
            logging.debug("#### jAEk succeeded")

        # save the data from jAEk if it exists
        outdata = {"domain": currentDomain}
        try:
            outdata = json.load(open("output-jaek.json"))
            os.unlink("output-jaek.json")
        except:
            pass
        saveDataAndExit("output.json", outdata)

        os.unlink(tmpin)
        if os.path.exists("similarities"):
            shutil.rmtree("similarities")
    #}}}

    logging.debug("###########################")
    logging.debug("########### DONE ##########")
    logging.debug("###########################")
    logging.debug("prescan.py is done")

