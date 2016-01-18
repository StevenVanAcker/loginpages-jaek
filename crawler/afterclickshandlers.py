#!/usr/bin/python

import logging, sys, json
from time import sleep
from urllib.parse import urljoin

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
    def __init__(self, srctype):
        self.links = []
        self.srctype = srctype
        self.pwFields = {}
        self.url = None
        self.initclick = None
        self.preclicks = []

    def getResult(self):
        return {
            "links": self.links,
            "srctype": self.srctype,
            "pwfields": self.pwFields,
            "url": self.url,
            "element_to_click": self.initclick.toDict() if self.initclick != None else None,
            "pre_clicks": [x.toDict() if x != None else None for x in self.preclicks],
        }

    def handle(self, data, errorcode):
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
#}}}

class LoginPageLogger(BaseAfterClicksHandler): #{{{
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

