import time
import logging
import sys

from PyQt5.Qt import QApplication
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWebKitWidgets import QWebView
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkProxy


from xvfbwrapper import Xvfb

globTimeout = 5

class MyNetworkAccessManager(QNetworkAccessManager): 
    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.sslErrors.connect(self._sslErrors)
        self.p = QNetworkProxy(QNetworkProxy.HttpProxy, "localhost", 8080, None, None)
        #self.setProxy(self.p)

    def createRequest(self, operation, request, data): 
        logging.debug("mymanager handles {}".format(request.url()))
        return QNetworkAccessManager.createRequest(self, operation, request, data) 

    def _sslErrors(self, reply, errors):
        logging.debug("sslErrors!! {} {}".format(reply, errors))


class Screenshot(QWebView):
    def __init__(self):
        QWebView.__init__(self)
        self.show()
        self.dontremove = MyNetworkAccessManager()
        self.page().setNetworkAccessManager(self.dontremove)
        self._loaded = False
        self.loadFinished.connect(self._loadFinished)
        self.loadStarted.connect(self._loadStarted)
        self.loadProgress.connect(self._loadProgress)

    def capture(self, url, output_file):
        self._file = output_file
        self.load(QUrl(url))

    def _loadFinished(self, result):
        self._loaded = True
        # set to webpage size
        frame = self.page().mainFrame()
        self.page().setViewportSize(frame.contentsSize())
        # render image
        image = QImage(self.page().viewportSize(), QImage.Format_ARGB32)
        painter = QPainter(image)
        frame.render(painter)
        painter.end()
        logging.debug('saving {}'.format(self._file))
        image.save(self._file)
        logging.debug("Load finished {}".format(result))

    def _loadStarted(self):
        logging.debug("Load started")

    def _loadProgress(self, result):
        logging.debug("Load progress {}".format(result))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s: %(levelname)s - %(message)s')
    vdisplay = Xvfb()
    vdisplay.start()
    app = QApplication(sys.argv)

    if len(sys.argv) < 2:
        logging.error("Usage: {} <url> [<timeout>]".format(sys.argv[0]))
        sys.exit(1)

    if len(sys.argv) > 2:
        globTimeout = int(sys.argv[2])

    s = Screenshot()
    s.capture(sys.argv[1], 'website.png')

    app.exec_()
    vdisplay.stop()

