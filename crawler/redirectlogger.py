from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from urllib.parse import urljoin
import logging, copy, pprint

class RedirectLoggerNetworkAccessManager(QNetworkAccessManager):
    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.finished.connect(self._finished)
        self.redirects = {}
        self.headers = {}
        self.stopLoggingFlag = False

    def stopLogging(self):
        self.stopLoggingFlag = True

    def getLoggedNetworkData(self):
        return {
            "redirects": self.redirects,
            "headers": self.headers
        }

    def setLoggedNetworkData(self, data):
        tmp = copy.deepcopy(data)
        self.redirects = tmp["redirects"]
        self.headers = tmp["headers"]

    def _logRedirect(self, fromurl, tourl):
        if self.stopLoggingFlag:
            logging.debug("RedirectLoggerNetworkAccessManager.stopLoggingFlag = True, refusing to log more.")
            return

        if fromurl not in self.redirects:
            fullurl = urljoin(fromurl, tourl)
            self.redirects[fromurl] = fullurl
        else:
            logging.debug("ERROR: _logRedirect(): previous redirect from {} to {} contradicts new target {}".format(fromurl, self.redirects[fromurl], tourl))

    def _logHeaders(self, url, headers):
        if self.stopLoggingFlag:
            logging.debug("RedirectLoggerNetworkAccessManager.stopLoggingFlag = True, refusing to log more.")
            return

        if url not in self.headers:
            self.headers[url] = headers
        else:
            logging.debug("ERROR: _logHeaders(): headers for {} already logged".format(url))


    def _finished(self, reply):
        httpcode = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        newloc = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        headers = dict([(str(h, encoding='utf8'), str(v, encoding='utf8')) for (h,v) in reply.rawHeaderPairs()])
        origurl = reply.request().url().toString()
        newurl = reply.request().url().toString()
        self._logHeaders(newurl, headers)
        if newloc != None:
            # 30x redirect
            logging.debug("URL redirect {} from {} to {}".format(httpcode, origurl, newloc.toString()))
            self._logRedirect(origurl, newloc.toString())

