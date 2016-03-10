#!/usr/bin/env python3

import os, urllib.request, json
from urllib.parse import urlparse

class HSTSPreloadList(object):
    def __init__(self, jsonfile=None, url=None, downloadIfNeeded=True): #{{{
        self.data = None
        self.jsonfile = jsonfile

        if url == None:
            self.url = 'https://code.google.com/p/cs/codesearch/codesearch/json?file_info_request=b&file_spec=b&package_name=chromium&name=src%2Fnet%2Fhttp%2Ftransport_security_state_static.json&file_spec=e&code_id=c0&read_from_cs_index=false&file_info_request=e'
        else:
            self.url = url
 
        if downloadIfNeeded:
            self._download()

        self._readFile()
        self._makeDict()
    #}}}
    def _download(self): #{{{
        if self.jsonfile == None or not os.path.isfile(self.jsonfile):
            (fn, _) = urllib.request.urlretrieve(self.url)
            data = json.load(open(fn))
            realdata = data["file_info_response"][0]["file_info"]["content"]["text"]
            realdata = "\n".join([x for x in realdata.split("\n") if not (x.strip().startswith("//") or x.strip() == "")])
            if self.jsonfile != None:
                with open(self.jsonfile, "w") as fp:
                    fp.write(realdata)
            os.unlink(fn)
            self.data = json.loads(realdata)
    #}}}
    def _readFile(self): #{{{
        if self.jsonfile != None:
            self.data = json.load(open(self.jsonfile))
    #}}}
    def _makeDict(self): #{{{
        if self.data != None:
            out = {}
            for r in self.data["entries"]:
                name = r["name"].lower()
                subs = r["include_subdomains"] if "include_subdomains" in r else False
                out[name] = subs
            self.data = out
    #}}}
    def getAllTopDomains(self, hostname): #{{{
        # generate a list of all domains to which this hostname is a subdomain
        out = []
        parts = hostname.split(".")

        for p in range(1,len(parts)+1):
            out += [".".join(parts[-p:])]
        return out
    #}}}
    def hostnameInList(self, hostname): #{{{
        hn = hostname.lower()

        # check if the hostname is in the list verbatim
        if hn in self.data:
            return True

        # check for topdomains where include_subdomains is true
        for h in self.getAllTopDomains(hn):
            if h in self.data and self.data[h]:
                return True
        return False
    #}}}
    def urlInList(self, url): #{{{
        urlparts = urlparse(url)
        return self.hostnameInList(urlparts.hostname)
    #}}}

if __name__ == "__main__":
    import sys, pprint
    h = HSTSPreloadList(jsonfile="FIXME")
    url = sys.argv[1]
    print("Is URL {} in HSTS preload list? {}".format(url, h.urlInList(url)))
