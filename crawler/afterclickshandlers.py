#!/usr/bin/python

import logging, sys, json
#from asyncio.tasks import sleep
from time import sleep

from models.clickable import Clickable

class BaseAfterClicksHandler(object): #{{{
    def handle(self, data):
        logging.info("BaseAfterClicksHandler doing nothing")

    @staticmethod
    def saveData(fn, url, initclick, preclicks):
        outdata = {}
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

class LoginPageLogger(BaseAfterClicksHandler): #{{{
    def __init__(self):
        self.counter = 0

    def handle(self, data):
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
        if any(viss):
            data["self"].screenshot("yespw{}.png".format(self.counter))
            self.saveData("yespw{}.json".format(self.counter), data["webpage"].url, initclick, preclicks)
        else:
            data["self"].screenshot("nopw{}.png".format(self.counter))
            self.saveData("nopw{}.json".format(self.counter), data["webpage"].url, initclick, preclicks)
        self.counter += 1
#}}}

class ScreenshotTaker(BaseAfterClicksHandler): #{{{
    def __init__(self):
        self.counter = 0

    def handle(self, data):
        logging.info("Sleeping 5 seconds...")
        sleep(5)
        logging.info("Taking screenshot of {}".format(data["webpage"].url))
        data["self"].screenshot("replay{}.png".format(self.counter))
        self.counter += 1
#}}}

