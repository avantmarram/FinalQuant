import requests, time
from urllib.parse import urlencode

PV_BASE = "https://api.patentsview.org/patents/query"

def fetch_patents(keywords):
    out = []
    for kw in keywords:
        # Spørring: finn i tittel
        q = '{"_text_any":{"patent_title":"%s"}}' % kw
        params = {
            "q": q,
            "f": "['patent_number','patent_date','patent_title']",
            "o": '{"per_page":10,"page":1,"order":"-patent_date"}'
        }
        url = PV_BASE + "?" + urlencode(params)

        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                continue
            for p in r.json().get("patents", []):
                out.append({
                    "source": "PatentsView",
                    "title": p.get("patent_title",""),
                    "number": p.get("patent_number",""),
                    "date": p.get("patent_date",""),
                    "keyword": kw,
                })
        except Exception:
            pass
        time.sleep(0.5)
    return out
