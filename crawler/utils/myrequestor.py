from time import time, sleep
import logging

from PyQt5.Qt import QEventLoop, QTimer, QUrl
from PyQt5.QtWebKitWidgets import QWebPage

from core.interactioncore import InteractionCore
from models.utils import CrawlSpeed


class MyRequestor(InteractionCore):
    def __init__(self, parent, proxy, port, crawl_speed = CrawlSpeed.Medium, afterClicksHandler=None):
        super(MyRequestor, self).__init__(parent, proxy, port, crawl_speed, afterClicksHandler=afterClicksHandler)
        self.resultToReturn = None
        self.doneLoading = False
        self.loadFinished.connect(self._loadFinished)

    def _loadFinished(self, result):
        # remember that we are done loading, or in case of failure, we are never done loading...
        self.doneLoading = result

        # we can now kill the timeout
        if self.timeoutTimer:
            self.timeoutTimer.stop()
            self.timeoutTimer = None

        if self.doneLoading:
            self.delayTimer = QTimer()
            self.delayTimer.setSingleShot(True)
            self.delayTimer.timeout.connect(self._delayTriggered)
            self.delayTimer.start(self.delayValue * 1000)
        else:
            newurl = self.mainFrame().url().toString()
            self.mainFrame().setHtml(None)
            self.resultToReturn = ("", newurl)

    def _delayTriggered(self):
        # when this triggers, we know the page loaded successfully, just return stuff
        newurl = self.mainFrame().url().toString()
        parsed_html = self.mainFrame().toHtml()
        self.mainFrame().setHtml(None)
        self.resultToReturn = (parsed_html, newurl)

    def _timeoutTriggered(self):
        # when timeout triggers, that means the page didn't finish loading yet and so the delaytimer is also not running yet
        # just stop loading and return
        self.triggerAction(QWebPage.Stop)
        newurl = self.mainFrame().url().toString()
        self.mainFrame().setHtml(None)
        self.resultToReturn = ("", newurl)

    def get(self, qurl, timeout = 10, delay = 60):
        self.delayValue = delay
        self.timeoutTimer = QTimer()
        self.timeoutTimer.setSingleShot(True)
        self.timeoutTimer.timeout.connect(self._timeoutTriggered)
        self.timeoutTimer.start(timeout * 1000)

        self.mainFrame().load(QUrl(qurl))

        while self.resultToReturn == None:
            sleep(0.1)
            self.app.processEvents()
        return self.resultToReturn

