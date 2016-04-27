#!/usr/bin/env python3

import sys, os, json
if sys.version_info >= (3, 0):
    from urllib.request import urlretrieve
    from urllib.parse import urlparse
else:
    from urllib import urlretrieve
    from urlparse import urlparse

class HPKPPreloadList(object):
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
            (fn, _) = urlretrieve(self.url)
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
                hstssubs = r["include_subdomains"] if "include_subdomains" in r else False
                hpkpsubs = r["include_subdomains_for_pinning"] if "include_subdomains_for_pinning" in r else False
                if "pins" in r:
                    out[name] = hstssubs or hpkpsubs
            self.data = out
    #}}}
    def clear(self): #{{{
        self.data = {}
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
        if hostname == None:
            return False

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
    def addDomain(self, dn, subs): #{{{
        oldsubs = False
        if dn in self.data:
            oldsubs = self.data[dn]
        self.data[dn] = subs or oldsubs
    #}}}
    def delDomain(self, dn, subs): #{{{
        if dn in self.data:
            self.data.pop(dn, None)

        # if subs, then delete all subdomains of the given domain too
        if subs:
            dotdn = "." + dn
            dellist = [k for (k,v) in self.data.items() if ("."+k).endswith(dotdn)]

            for d in dellist:
                self.data.pop(d, None)
    #}}}

if __name__ == "__main__":
    import sys, pprint
    h = HPKPPreloadList(jsonfile="FIXME")
    url = sys.argv[1]
    print("Is URL {} in HPKP preload list? {}".format(url, h.urlInList(url)))
