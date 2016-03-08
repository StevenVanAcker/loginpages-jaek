from asyncio.tasks import sleep
import logging
import sys

from PyQt5.Qt import QApplication, QObject
from PyQt5.QtNetwork import QNetworkAccessManager
from PyQt5.QtCore import QSize, QUrl

from core.eventexecutor import EventExecutor, XHRBehavior, EventResult
from core.jaekcore import JaekCore
from utils.myrequestor import MyRequestor
from xvfbwrapper import Xvfb
from models.utils import CrawlSpeed
from models.webpage import WebPage

from afterclickshandlers import ScreenshotTaker

# class to replay a series of clicks on a webpage

class Replayer(JaekCore):
    def __init__(self, proxy="", port=0, afterClicksHandler=None):
        QObject.__init__(self)
        self.app = QApplication(sys.argv)
        self._network_access_manager = None #QNetworkAccessManager(self)

        self._afterClicksHandler=afterClicksHandler

        self._event_executor = EventExecutor(self, proxy, port, crawl_speed=CrawlSpeed.Speed_of_Lightning,
             network_access_manager=self._network_access_manager, afterClicksHandler=self._afterClicksHandler)

        self.requestor = MyRequestor(self, proxy, port, afterClicksHandler=self._afterClicksHandler)

    def replay(self, url, click=None, preclicks=[], timeout=60):
        pagehtml, newurl = self.requestor.get(QUrl(url), delay=20, timeout=timeout)

        self._event_executor.stopLogging()
        self._event_executor.setLoggedNetworkData(self.requestor.getLoggedNetworkData())

        logging.debug("Requestor is at {}".format(newurl))
        if newurl == "":
            # couldn't load
            return EventResult.ErrorWhileInitialLoading, None
        webpage = WebPage(0, newurl, pagehtml)
        errorcode, deltapage = self._event_executor.execute(webpage, element_to_click=click, pre_clicks=preclicks, xhr_options=XHRBehavior.ObserveXHR, timeout=timeout)
        if click != None and deltapage == None:
            logging.info("Replay failed!")
        return errorcode, deltapage

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    vdisplay = Xvfb()
    vdisplay.start()
       
    sst = ScreenshotTaker()
    url, initclick, preclicks = sst.loadData(sys.argv[1]) # This is ugly, unserializing data should not happen in afterClicksHandlers

    logging.info("URL = {}".format(url))
    logging.info("initclick = {}".format(initclick.toString() if initclick != None else "<None>"))
    logging.info("preclicks = {}".format([x.toString() if x != None else "<None>" for x in preclicks]))

    rep = Replayer(afterClicksHandler=sst)
    rep.replay(url, initclick, preclicks)

    vdisplay.stop()

