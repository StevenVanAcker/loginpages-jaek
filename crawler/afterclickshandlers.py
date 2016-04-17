#!/usr/bin/python

import logging, sys, json, pprint
from time import sleep
from urllib.parse import urljoin, urlparse, ParseResult

from models.clickable import Clickable
from core.eventexecutor import EventResult
from HSTSPreloadList import HSTSPreloadList

class BaseAfterClicksHandler(object): #{{{
    def handle(self, data, errorcode):
        logging.info("BaseAfterClicksHandler doing nothing")

    @staticmethod
    def saveData(fn, url, initclick, preclicks, other=None):
        outdata = {} if other == None else other
        outdata["url"] = url
        outdata["element_to_click"] = initclick.toDict() if initclick != None else None
        outdata["pre_clicks"] = [x.toDict() if x != None else None for x in preclicks]

        json.dump(outdata, open(fn, "w"))

    @staticmethod
    def loadData(fn):
        indata = json.load(open(fn))
        url = indata["url"]
        initclick = Clickable.fromDict(indata["element_to_click"]) if indata["element_to_click"] != None else None
        preclicks = [Clickable(None,None,None).fromDict(x) if x != None else None for x in indata["pre_clicks"]]
        return url, initclick, preclicks
#}}}









class LoginPageChecker(BaseAfterClicksHandler): #{{{
    def __init__(self, srctype, origurl, hstspreloadchecker, domain = None, autoExitFilename = None): #{{{
        self.links = []
        self.srctype = srctype
        self.domain = domain
        logging.debug("LoginPageChecker set domain to {}".format(self.domain))
        self.HSTSPreloadListChecker = hstspreloadchecker
        self.autoExitFilename = autoExitFilename

        # toplevel URLs that have no path (e.g. http://test.com)
        # should be converted to end in / (http://test.com/)
        # otherwise things are messed up. WebKit translates http://test.com to http://test.com/ automagically
        # which messes up the redirect chain. So perform this translation even before Webkit does it.
        urlparts = urlparse(origurl)
        if urlparts.path == "":
            urlparts = ParseResult(urlparts[0], urlparts[1], "/", urlparts[3], urlparts[4], urlparts[5])
            origurl = urlparts.geturl()

        self.origurl = origurl
        self.pwFields = {}
        self.url = None
        self.initclick = None
        self.preclicks = []
        self.resultFlag = False

        self.redirectPageResources = {}
        self.mainRedirectChain = []
#}}}
    def hasResult(self): #{{{
        return self.resultFlag
#}}}
    def getResult(self): #{{{
        return {
            "domain": self.domain,
            "links": self.links,
            "srctype": self.srctype,
            "pwfields": self.pwFields,
            "url": self.url,
            "origurl": self.origurl,
            "element_to_click": self.initclick.toDict() if self.initclick != None else None,
            "pre_clicks": [x.toDict() if x != None else None for x in self.preclicks],
            "redirectPageResources": self.redirectPageResources,
            "mainRedirectChain": self.mainRedirectChain,
            "success": True
        }
#}}}
    def getResourceData(self, url, page): #{{{
        outdata = {}

        # check CSP and other HTTP headers
        uir = False
        bamc = False
        # 1. get network data for current URL
        nwdata = page.getLoggedNetworkData()
        if "headers" in nwdata and url in nwdata["headers"]:
            currentheaders = nwdata["headers"][url]

            # 2. check for HTTP header
            # there can be multiple HTTP headers...
            csplisthttp = [v for (k,v) in currentheaders.items() if k.lower() == "content-security-policy"]
            uirlisthttp = [v for (k,v) in currentheaders.items() if k.lower() == "upgrade-insecure-requests"]

            # 3. check for same headers as <meta> elements
            elements = page.mainFrame().findAllElements('meta')
            csplistmeta = [e.attribute("content", "").strip() for e in elements if e.attribute("http-equiv", "").lower().strip() == "content-security-policy"]
            uirlistmeta = [e.attribute("content", "").strip() for e in elements if e.attribute("http-equiv", "").lower().strip() == "upgrade-insecure-requests"]

            csplist = csplisthttp + csplistmeta
            uirlist = uirlisthttp + uirlistmeta

            uir = any("upgrade-insecure-requests" in l.lower() for l in csplist) or len(uirlist) > 0
            bamc = any("block-all-mixed-content" in l.lower() for l in csplist)
        else:
            logging.debug("Couldn't find the headers :(")

        
        # Find script resources
        elements = page.mainFrame().findAllElements('script')
        pairs = [(s.attribute("src", "").strip(), s.attribute("type", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = {}
        for (s, t, sri) in pairs:
            if s != "":
                nt = None
                if t == "" or "javascript" in t.lower():
                    nt = "javascript"
                if"vbscript" in t.lower():
                    nt = "vbscript"
                if nt != None:
                    ns = urljoin(url, s)
                    urls[ns] = { "type": nt, "sri": sri!="", "uir": uir, "bamc": bamc}
        outdata["script"] = urls

        # Find css resources
        elements = page.mainFrame().findAllElements('link[rel="stylesheet"]')
        pairs = [(s.attribute("href", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = {}
        for (s, sri) in pairs:
            if s != "":
                ns = urljoin(url, s)
                urls[ns] = { "sri": sri!="", "uir": uir, "bamc": bamc}
        outdata["css"] = urls

        # Find object resources
        elements = page.mainFrame().findAllElements('object')
        pairs = [(s.attribute("data", "").strip(), s.attribute("type", "").strip(), s.attribute("typemustmatch", "false"), s.attribute("classid", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = {}
        for (d, t, tmm, classid, sri) in pairs:
            logging.debug("Detected Object: {} {} {} {} {}".format(d, t, tmm, classid, sri))
            nsri = (sri!="")
            ntmm = (tmm.lower()=="true")
            if d != "":
                nt = "UNKNOWN---{}".format(classid.lower())
                if classid.lower() == "clsid:d27cdb6e-ae6d-11cf-96b8-444553540000":
                    nt = "flash"
                if "flash" in t.lower():
                    nt = "flash"

                if classid.lower().startswith("clsid:CAFEEFAC-00".lower()) and classid.lower().endswith("13-0001-FFFF-ABCDEFFEDCBA".lower()):
                    nt = "java"
                if "java" in t.lower():
                    nt = "java"

                if "silverlight" in t.lower():
                    nt = "silverlight"
                    
                if nt != "":
                    nd = urljoin(url, d)
                    urls[nd] = {"sri": nsri, "typemustmatch": ntmm, "type": nt, "uir": uir, "bamc": bamc}

        outdata["object"] = urls

        # Find embed resources
        elements = page.mainFrame().findAllElements('embed')
        pairs = [(s.attribute("src", "").strip(), s.attribute("type", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = {}
        for (s, t, sri) in pairs:
            logging.debug("Detected Embed: {} {} {}".format(s,t,sri))
            nsri = (sri!="")
            if s != "":
                nt = ""
                if "flash" in t.lower():
                    nt = "flash"
                if t == "" and s.lower().endswith(".swf"):
                    nt = "flash"

                if "java" in t.lower():
                    nt = "java"
                if t == "" and s.lower().endswith((".jar", ".class", ".jnlp")):
                    nt = "java"

                if t == "" and s.lower().endswith(".xap"):
                    nt = "silverlight"
                    
                if nt != "":
                    nd = urljoin(url, s)
                    urls[nd] = {"sri": nsri, "type": nt, "uir": uir, "bamc": bamc}

        outdata["embed"] = urls

        # Find applet resources
        elements = page.mainFrame().findAllElements('applet')
        pairs = [(s.attribute("archive", "").strip(), s.attribute("code", "").strip(), s.attribute("codebase", "").strip(), s.attribute("object", "").strip(), s.attribute("src", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = []
        for (a, c1, c2, o, s, sri) in pairs:
            logging.debug("Detected Applet: {} {} {} {} {} {}".format(a, c1, c2, o, s, sri))
            nsri = (sri!="")
            [a, c1, c2, o, s] = [urljoin(url, x) if x != "" else "" for x in [a, c1, c2, o, s]]
            if (a, c1, c2, o, s) != ("", "", "", "", ""):
                urls.append((a, c1, c2, o, s, sri, uir, bamc))

        outdata["applet"] = urls

        # augment the resource data with redirects
        for (k,v) in outdata.items():
            # we don't care about applets since they are like voodoo when it comes to specifying URL
            if k != "applet":
                for (u,v2) in v.items():
                    v2["redirectchain"] = self.buildNetworkTrace(u, page)

        return outdata
#}}}
    def handle(self, data, errorcode): #{{{
        self.initclick = data["element_to_click"]
        self.preclicks = data["pre_clicks"]
        self.url = data["webpage"].url

        base = data["self"].mainFrame().baseUrl().toString()
        for x in data["self"].mainFrame().findAllElements('a'):
            href = x.attribute("href", None)
            txt = x.toPlainText()
            if href != None:
                self.links.append( (urljoin(base, href), txt) )

        passwordfields = data["self"].mainFrame().findAllElements('input[type="password"]')
        self.pwFields = {}
        for pwf in passwordfields:
            xpath = pwf.evaluateJavaScript("getXPath(this)")
            isvis = pwf.evaluateJavaScript("jaek_isVisible(this)")
            formtarget = pwf.evaluateJavaScript("jaek_FormTargetFromPW(this)")
            taintedcss = pwf.evaluateJavaScript("jaek_hastaintedCSS(this)")
            if formtarget:
                formtarget = urljoin(base, formtarget)
            else:
                formtarget = None
            self.pwFields[xpath] = {
                "isVisible": isvis,
                "formTarget": formtarget,
                "taintedCSS": taintedcss
            }
        logging.debug("Logging something so that jAEK doesn't crap out...")

        ####################
        # Building the information about the main page redirect chain
        ####################
        self.mainRedirectChain = self.buildNetworkTrace(self.origurl, data["self"])

        ####################
        # Detect if any out-of-band authentication was used. 
        # For authentication in HTTP, we check www-authenticate
        # For SSL-based authentication, we log the hostname:port and do a check afterwards
        ####################

        for r in self.mainRedirectChain:
            if "headers" in r and "url" in r and r["headers"] != None:
                h = r["headers"]

                authtypes = list(set([v.split(" ")[0].lower() for (k,v) in h.items() if k.lower() == "WWW-Authenticate".lower()]))
                for a in authtypes:
                    logging.debug("AuthType {} by {}".format(a, r["url"]))
                    self.observeStuff("authtypes", a)

            if "sslinfo" in r and "url" in r and r["sslinfo"] != None:
                urlparts = urlparse(r["url"])
                if urlparts.scheme.lower() == "https":
                    netloc = "{}:{}".format(urlparts.hostname, urlparts.port if urlparts.port != None else 443)
                    self.observeStuff("sslhostports", netloc)

        # Can we exit jAEk at this point?
        # if we are on the same domain and this page has pwfields, then yes
        if len(passwordfields) > 0:
            if not self.urlInDomain(self.url):
                logging.debug("Found a login page, but not in domain {}: {}".format(self.url, self.domain))
            else:
                data["self"].screenshot("screenshot.png")
                if self.hasResult() and self.autoExitFilename != None:
                    res = self.getResult()
                    # these will be bogus when running jAEk because it doesn't reset the arrays on every page
                    res["redirectPageResources"] = None
                    res["links"] = None
                    with open(self.autoExitFilename, 'w') as outfile:
                        json.dump(res, outfile)
                    sys.exit(0)

        self.resultFlag = True
#}}}
    def handleRedirectPage(self, url, data): #{{{
        if url == None:
            return

        if url not in self.redirectPageResources:
            x = self.getResourceData(url, data)
            self.redirectPageResources[url] = x
        else:
            logging.debug("Afterclickhandler: not logging resources for URL {}, since we already visited it earlier.".format(url))
#}}}
    def buildNetworkTrace(self, url, data): #{{{
        '''
        From the supplied data, reconstruct the redirect chain with HTTP headers and SSL information for each hop.
        This information also includes a set of flags that can help determine whether a resource is loaded securely or not.
        Returns a list
        '''
        out = []
        currurl = url
        nextcode = None
        redirectlist = []

        networkdata = data.getLoggedNetworkData()

        while currurl != None:
            h = networkdata["headers"][currurl] if currurl in networkdata["headers"] else None
            s = networkdata["sslinfo"][currurl] if currurl in networkdata["sslinfo"] else None
            nextcode = networkdata["redirects"][currurl]["httpcode"] if currurl in networkdata["redirects"] else None
            redirectlist += [currurl]
            nexturl = networkdata["redirects"][currurl]["url"] if currurl in networkdata["redirects"] else None

            # HTTP Strict Transport Security
            hstspreload = self.HSTSPreloadListChecker.urlInList(currurl)
            hstsZeroAge = False
            hstsIncludeSubs = False
            hstsset = False
            if h != None:
                hstsheaders = [v for (k,v) in h.items() if k.lower() == "strict-transport-security"]
                hstsZeroAge = any("max-age=0" in l.lower() for l in hstsheaders)
                hstsIncludeSubs = any("includesubdomains" in l.lower() for l in hstsheaders)
                hstsset = len(hstsheaders) > 0

            # HTTP Public Key Pins
            hpkpZeroAge = False
            hpkpIncludeSubs = False
            hpkpset = False
            if h != None:
                hpkpheaders = [v for (k,v) in h.items() if k.lower() == "public-key-pins"]
                hpkpZeroAge = any("max-age=0" in l.lower() for l in hpkpheaders)
                hpkpIncludeSubs = any("includesubdomains" in l.lower() for l in hpkpheaders)
                hpkpset = len(hpkpheaders) > 0

            out.append({
                "url": currurl,
                "nexturl": nexturl,
                "headers": h,
                "sslinfo": s,
                "nextRedirectViaHttpcode": nextcode,
                "loadSucceeded": h != None and h != {},
                "HSTSPreload": hstspreload,
                "HSTSSet": hstsset,
                "HSTSZeroAge": hstsZeroAge,
                "HSTSIncludeSubs": hstsIncludeSubs,
                "HPKPSet": hpkpset,
                "HPKPZeroAge": hpkpZeroAge,
                "HPKPIncludeSubs": hpkpIncludeSubs,
            })

            currurl = nexturl
            if currurl in redirectlist:
                logging.debug("Redirect chain loops back to {} -> stopping loop".format(currurl))
                currurl = None

        return out
#}}}
    def urlInDomain(self, url): #{{{
        urlparts = urlparse(url)
        hostname = "." + urlparts.netloc.split(":")[0]

        return hostname.endswith("."+self.domain)
    #}}}
    def observeStuff(self, t, val): #{{{
        indata = {}
        fn = "{}.json".format(t)
        try:
            indata = json.load(open(fn))
        except:
            pass

        if val not in indata:
            indata[val] = 0
        indata[val] += 1

        logging.debug("Observing '{}' value '{}'".format(t, val))

        with open(fn, "w") as fp:
            json.dump(indata, fp)
    #}}}
#}}}

class ScreenshotTaker(BaseAfterClicksHandler): #{{{
    def __init__(self):
        self.counter = 0

    def handle(self, data, errorcode):
        logging.info("Sleeping 5 seconds...")
        sleep(5)
        logging.info("Taking screenshot of {}".format(data["webpage"].url))
        data["self"].screenshot("replay{}.png".format(self.counter))
        self.counter += 1
#}}}

