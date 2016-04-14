import time
import logging
import sys

from PyQt5.Qt import QApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWebKitWidgets import QWebView
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkProxy


globTimeout = 5

class MyNetworkAccessManager(QNetworkAccessManager):
    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.sslErrors.connect(self._sslErrors)
        self.finished.connect(self._finished)

        #self.p = QNetworkProxy(QNetworkProxy.HttpProxy, "localhost", 8080, None, None)
        #self.setProxy(self.p)

    def createRequest(self, operation, request, data):
        logging.debug("mymanager handles {}".format(request.url()))
        return QNetworkAccessManager.createRequest(self, operation, request, data)

    def _finished(self, reply):
        #logging.debug("mymanager finished reply {}".format(reply))
        logging.debug("mymanager finished reply for {}".format(reply.request().url()))
        logging.debug("   Errorstring: {}".format(reply.errorString()))
        logging.debug("   Errorcode: {}".format(reply.error()))
        logging.debug("   Headers:")
        for k,v in reply.rawHeaderPairs():
            logging.debug("       {}: {}".format(k, v))

    def _sslErrors(self, reply, errors):
        logging.debug("sslErrors!! {} {}".format(reply, errors))


class Screenshot(QWebView):
    def __init__(self, parent):
        self.app = parent #QApplication(sys.argv)
        QWebView.__init__(self)
        #self.dontremoveold = self.page().networkAccessManager()
        #self.dontremove = MyNetworkAccessManager(self.dontremoveold)
        self.dontremove = MyNetworkAccessManager()
        self.page().setNetworkAccessManager(self.dontremove)
        self.page().setForwardUnsupportedContent(True)
        self._loaded = False
        self.loadFinished.connect(self._loadFinished)
        self.loadStarted.connect(self._loadStarted)
        self.loadProgress.connect(self._loadProgress)

    def capture(self, url, output_file):
        self.load(QUrl(url))
        self.wait_load(globTimeout)
        self.wait_load(globTimeout, justwait=True)

        # set to webpage size
        frame = self.page().mainFrame()
        frame.securityOrigin().addLocalScheme("chrome-extension")
        logging.debug("local schemes = {}".format(frame.securityOrigin().localSchemes()))

        self.page().setViewportSize(frame.contentsSize())
        # render image
        image = QImage(self.page().viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        frame.render(painter)
        painter.end()
        logging.debug('saving {}'.format(output_file))
        image.save(output_file)

    def wait_load(self, maxwait, delay=0, justwait=False):
        # process app events until page loaded
        start = time.time()
        counter = 0
        while (not self._loaded or justwait) and time.time() < start + maxwait:
            self.app.processEvents()
            if counter == 0:
                logging.debug("Waiting {} seconds".format(maxwait))
            else:
                logging.debug("Waiting another {} seconds".format(maxwait - counter))
            time.sleep(1)
            counter += 1

        if not justwait:
            self._loaded = False

    def _loadFinished(self, result):
        self._loaded = True
        logging.debug("Load finished {}".format(result))

    def _loadStarted(self):
        logging.debug("Load started")

    def _loadProgress(self, result):
        logging.debug("Load progress {}".format(result))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    app = QApplication(sys.argv)

    if len(sys.argv) < 2:
        logging.error("Usage: {} <url> [<timeout>]".format(sys.argv[0]))
        sys.exit(1)

    if len(sys.argv) > 2:
        globTimeout = int(sys.argv[2])

    s = Screenshot(app)
    s.capture(sys.argv[1], 'website.png')

    app.exec_()
