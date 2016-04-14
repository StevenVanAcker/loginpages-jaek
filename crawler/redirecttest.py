import sys, os, pprint
from PyQt5.Qt import QApplication
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtWebKitWidgets import QWebView, QWebPage
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from urllib.parse import urljoin

class RedirectLoggerNetworkAccessManager(QNetworkAccessManager):
    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.finished.connect(self._finished)
        self.redirects = {}

    def createRequest(self, operation, request, data):
        #print("mymanager handles {}".format(request.url()))
        return QNetworkAccessManager.createRequest(self, operation, request, data)

    def _logRedirect(self, fromurl, tourl):
        if fromurl not in self.redirects:
            self.redirects[fromurl] = urljoin(fromurl, tourl)
        else:
            print("ERROR: _logRedirect(): previous redirect from {} to {} contradicts new target {}".format(fromurl, self.redirects[fromurl], tourl))
        
    def _finished(self, reply):
        httpcode = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        newloc = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        if newloc:
            print("URL redirect {} from {} to {}".format(httpcode, reply.request().url().toString(), newloc.toString()))
            self._logRedirect(reply.request().url().toString(), newloc.toString())


class RedirectLoggerWebPage(QWebPage):
    def __init__(self, p):
        QWebPage.__init__(self, p)
        self.mainFrame().urlChanged.connect(self._urlChanged)
        self.loadStarted.connect(self._loadStarted)
        self.previousUrl = None
        self.nam = RedirectLoggerNetworkAccessManager()
        self.setNetworkAccessManager(self.nam)


    def _urlChanged(self, newurl):
        if self.previousUrl != None and newurl.toString() == self.previousUrl.toString():
            # ignore this...
            return

        if self.previousUrl == None:
            print("URL Changed from None to {}".format(newurl.toString()))
        else:
            print("URL Changed from {} to {}".format(self.previousUrl.toString(), newurl.toString()))
        self.previousUrl = newurl

    def _loadStarted(self):
        newurl = self.mainFrame().requestedUrl()
        if self.previousUrl != None and newurl.toString() == self.previousUrl.toString():
            # ignore this...
            return

        if self.previousUrl == None:
            print("X URL Changed from None to {}".format(newurl.toString()))
        else:
            print("X URL Changed from {} to {}".format(self.previousUrl.toString(), newurl.toString()))
            self.networkAccessManager()._logRedirect(self.previousUrl.toString(), newurl.toString())
        self.previousUrl = newurl

    def javaScriptConsoleMessage(self, msg, line, sid):
        #print("CONSOLE: {}".format(msg))
        pass

    def userAgentForUrl(self, url):
        ''' Returns a User Agent that will be seen by the website. '''
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36"


if __name__ == "__main__":
    def timer_func():
        global app, nam
        #print("Done")
        print("REDIECTS: {}".format(pprint.pformat(nam.redirects)))
        app.exit(0)

    url = sys.argv[1]

    app = QApplication(sys.argv)


    wv = QWebView()
    wv.app = app

    wp = RedirectLoggerWebPage(wv)
    wv.setPage(wp)

    timer = QTimer()
    timer.timeout.connect(timer_func)
    timer.start(60*1000)

    wv.load(QUrl(url))

    app.exec_()
    #print("Exiting")

