#!/usr/bin/python

import logging, sys, json, pprint
from time import sleep
from urllib.parse import urljoin, urlparse, ParseResult

from models.clickable import Clickable
from core.eventexecutor import EventResult

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
    def __init__(self, srctype, origurl):
        self.links = []
        self.srctype = srctype

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



    def hasResult(self):
        return self.resultFlag

    def getResult(self):
        return {
            "links": self.links,
            "srctype": self.srctype,
            "pwfields": self.pwFields,
            "url": self.url,
            "origurl": self.origurl,
            "element_to_click": self.initclick.toDict() if self.initclick != None else None,
            "pre_clicks": [x.toDict() if x != None else None for x in self.preclicks],
        }

    def getResourceData(self, url, page):
        logging.debug("Retrieving resources from {}".format(url))
        outdata = {}
        
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
                    urls[ns] = { "type": nt, "sri": sri!=""}
        outdata["script"] = urls

        # Find css resources
        elements = page.mainFrame().findAllElements('link[rel="stylesheet"]')
        pairs = [(s.attribute("href", "").strip(), s.attribute("integrity", "")) for s in elements]
        urls = {}
        for (s, sri) in pairs:
            if s != "":
                ns = urljoin(url, s)
                urls[ns] = { "sri": sri!=""}
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
                nt = ""
                if classid.lower() == "clsid:d27cdb6e-ae6d-11cf-96b8-444553540000":
                    nt = "flash"
                if "flash" in t.lower():
                    nt = "flash"

                if classid.lower().startswith("clsid:CAFEEFAC-00".lower()) and classid.lower().endswith("13-0001-FFFF-ABCDEFFEDCBA".lower()):
                    nt = "java"
                if "java" in t.lower():
                    nt = "java"
                    
                if nt != "":
                    nd = urljoin(url, d)
                    urls[nd] = {"sri": nsri, "typemustmatch": ntmm, "type": nt}

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
                    
                if nt != "":
                    nd = urljoin(url, s)
                    urls[nd] = {"sri": nsri, "type": nt}

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
                urls.append((a, c1, c2, o, s, sri))

        outdata["applet"] = urls
        return outdata

    def handle(self, data, errorcode): #{{{
        self.initclick = data["element_to_click"]
        self.preclicks = data["pre_clicks"]
        self.url = data["webpage"].url

        base = data["self"].mainFrame().baseUrl().toString()
        for x in data["self"].mainFrame().findAllElements('a'):
            href = x.attribute("href", None)
            if href != None:
                self.links.append(urljoin(base, href))

        passwordfields = data["self"].mainFrame().findAllElements('input[type="password"]')
        self.pwFields = dict([(p.evaluateJavaScript("getXPath(this)"), p.evaluateJavaScript("jaek_isVisible(this)")) for p in passwordfields])
        logging.debug("Logging something so that jAEK doesn't crap out...")
        if len(passwordfields) > 0:
            data["self"].screenshot("screenshot.png")

        logging.info("Resources:")
        logging.info(pprint.pformat(self.getResourceData(self.url, data["self"])))


        # TODO main page:
        #    check redirect chain. Do we have an HTTP hop?
        #    <HTTPSVULN>
        #    is the form target set to HTTPS?
        #        the form target can not redirect through HTTP, since POST requests can not have a redirect without a HTTP 307 code which triggers user interaction
        #        <HTTPSVULN>

        # TODO for resources, form the main page:
        #    is CSP set with upgrade-insecure-resources?
        #    is HTTP upgrade-insecure-resources header set?
        #    is SRI set?
        
        # TODO for each resource:
        #    is the resource loaded over HTTP? does the redirect chain have HTTP?
        #    <HTTPSVULN>

        # "HTTPSVULN" for any HTTPS URL:
        #    is HSTS set? what is max-age?
        #    is the hostname on the HSTS preload list?
        #    is the key pinned?
        #    is the key pinned in the browser?
        #    does the host have SSL vulns?
        # https://github.com/rbsec/sslscan
        # https://github.com/okoeroo/drssl
        # https://github.com/nabla-c0d3/sslyze
        # BEAST, Lucky Thirteen, BREACH, POODLE, Heartbleed, FREAK, DROWN, CRIME, LogJam

        '''
                data = {
                    "mainpage": [
                    { "url": "...",
                      "httpcode": None | 301,
                      "headers": [ ],
                      "sslinfo": [ ],
                    }]
                    "resources": [{
                      "type": ...
                      "sri": ...
                      "redirectchain": [{
                          "url": ...,
                          "httpcode": ...,
                          "headers": ...,
                          "sslinfo": ...
                      }]
                    }]
                    "formtarget": [{
                          "url": ...,
                          "httpcode": ...,
                          "headers": ...,
                          "sslinfo": ...
                      }],
                    "pwfield": {
                    }
                    }
                }
        '''

        out = {}
        networkdata = data["self"].getLoggedNetworkData()
        logging.info("Network Data:")
        logging.info(pprint.pformat(networkdata))
        print("-------------------------")
        print("-------------------------")
        print("-------------------------")
        
        ####################
        # Building the information about the main page redirect chain
        ####################
        out["mainpage"] = []
        currurl = self.origurl
        nextcode = None
        redirectlist = []

        while currurl != None:
            h = networkdata["headers"][currurl] if currurl in networkdata["headers"] else None
            s = networkdata["sslinfo"][currurl] if currurl in networkdata["sslinfo"] else None
            nextcode = networkdata["redirects"][currurl]["httpcode"] if currurl in networkdata["redirects"] else None
            redirectlist += [currurl]
            nexturl = networkdata["redirects"][currurl]["url"] if currurl in networkdata["redirects"] else None

            out["mainpage"].append({
                "url": currurl,
                "nexturl": nexturl,
                "headers": h,
                "sslinfo": s,
                "nextRedirectViaHttpcode": nextcode,
            })

            currurl = nexturl
            if currurl in redirectlist:
                logging.debug("Redirect chain loops back to {} -> stopping loop".format(currurl))
                currurl = None

        ####################
        # Building the information about the resources loaded from the main page
        ####################
        logging.debug("For science!! remove the following line")
        out = {} # FIXME
        out["resources"] = []

        logging.info(pprint.pformat(out))

        self.resultFlag = True
#}}}
    def handleRedirectPage(self, data): #{{{
        logging.info("afterClickHandler.handleRedirectPage says {}".format(data.mainFrame().toHtml()))
#}}}
#}}}

class UnusedLoginPageLogger(BaseAfterClicksHandler): #{{{
    def __init__(self):
        self.counter = 0

    def handle(self, data, errorcode):
        #logging.info(data["self"].mainFrame().toHtml())

        #if errorcode == EventResult.TargetElementNotFound:
        #    logging.info("Recorded some error! HTML is ")
        #    logging.info(data["self"].mainFrame().toHtml())

        initclick = data["element_to_click"]
        preclicks = data["pre_clicks"]
        allclicks = []
        if initclick:
            allclicks.append(initclick.toDict())
        if preclicks:
            allclicks.extend([x.toDict() for x in preclicks])

        passwordfields = data["self"].mainFrame().findAllElements('input[type="password"]')

        xps = [p.evaluateJavaScript("getXPath(this)") for p in passwordfields]
        viss = [p.evaluateJavaScript("jaek_isVisible(this)") for p in passwordfields]

        for i in range(len(xps)):
            xp = xps[i]
            vis = viss[i]
            logging.debug("    ({}) password field {}: {}".format(vis, xp, passwordfields[i].toOuterXml()))

        logging.info("Taking screenshot of {} with clicks: {}".format(data["webpage"].url, json.dumps(allclicks)))
        if len(passwordfields) > 0: #any(viss):
            data["self"].screenshot("yespw{}.png".format(self.counter))
            self.saveData("yespw{}.json".format(self.counter), data["webpage"].url, initclick, preclicks)
            logging.info("Found a password field, exiting")
            sys.exit(0)
        else:
            data["self"].screenshot("nopw{}.png".format(self.counter))
            self.saveData("nopw{}.json".format(self.counter), data["webpage"].url, initclick, preclicks)
        self.counter += 1
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

