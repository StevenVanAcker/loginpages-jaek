from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QSslCertificate, QSsl
from urllib.parse import urljoin
import logging, copy, pprint

class RedirectLoggerNetworkAccessManager(QNetworkAccessManager):
    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.finished.connect(self._finished)
        self.encrypted.connect(self._encrypted)
        self.redirects = {}
        self.headers = {}
        self.sslinfo = {}
        self.stopLoggingFlag = False

    def stopLogging(self):
        self.stopLoggingFlag = True

    def getLoggedNetworkData(self):
        return {
            "redirects": self.redirects,
            "headers": self.headers,
            "sslinfo": self.sslinfo,
        }

    def setLoggedNetworkData(self, data):
        tmp = copy.deepcopy(data)
        self.redirects = tmp["redirects"]
        self.headers = tmp["headers"]
        self.sslinfo = tmp["sslinfo"]

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

    def _logSSLInfo(self, url, proto, cipher, certs):
        if self.stopLoggingFlag:
            logging.debug("RedirectLoggerNetworkAccessManager.stopLoggingFlag = True, refusing to log more.")
            return

        if url not in self.sslinfo:
            self.sslinfo[url] = {
                "proto": proto,
                "cipher": cipher,
                "certs": certs
            }
        else:
            logging.debug("ERROR: _logSSLInfo(): headers for {} already logged".format(url))

    def _finished(self, reply):
        httpcode = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        newloc = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        headers = dict([(str(h, encoding='utf8'), str(v, encoding='utf8')) for (h,v) in reply.rawHeaderPairs()])
        origurl = reply.request().url().toString()
        self._logHeaders(origurl, headers)
        if newloc != None:
            # 30x redirect
            logging.debug("URL redirect {} from {} to {}".format(httpcode, origurl, newloc.toString()))
            self._logRedirect(origurl, newloc.toString())

    def sslProtoName(self, p):
        plist = {
            QSsl.SslV3: "QSsl::SslV3",
            QSsl.SslV2: "QSsl::SslV2",
            QSsl.TlsV1_0: "QSsl::TlsV1_0",
            QSsl.TlsV1_1: "QSsl::TlsV1_1",
            QSsl.TlsV1_2: "QSsl::TlsV1_2",
            QSsl.TlsV1SslV3: "QSsl::TlsV1SslV3",
        }
        return plist[p] if p in plist else "QSsl::UnknownProtocol"

    def certificateSummary(self, cert):
        fields = [
         ("O", QSslCertificate.Organization),
         ("CN", QSslCertificate.CommonName),
         ("L", QSslCertificate.LocalityName),
         ("OU", QSslCertificate.OrganizationalUnitName),
         ("C", QSslCertificate.CountryName),
         ("ST", QSslCertificate.StateOrProvinceName),
         ("DN", QSslCertificate.DistinguishedNameQualifier),
         ("serial", QSslCertificate.SerialNumber),
         ("email", QSslCertificate.EmailAddress)
        ]
        outlist = []
        for (n, t) in fields:
            v = ", ".join(cert.issuerInfo(t))
            if v != "":
                outlist.append("{}={}".format(n, v))
        return "/".join(outlist)

    def _encrypted(self, reply):
        origurl = reply.request().url().toString()
        logging.debug("SSL handshake completed for {}".format(origurl))

        sslconf = reply.sslConfiguration()
        cipher = sslconf.sessionCipher().name()
        proto = self.sslProtoName(sslconf.sessionProtocol())
        certs = [(self.certificateSummary(x), str(x.toPem(), "utf8")) for x in sslconf.peerCertificateChain()]
        self._logSSLInfo(origurl, proto, cipher, certs)

