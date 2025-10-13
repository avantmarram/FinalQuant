import requests, time
GDELT="https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=ArtList&maxrecords=10&format=json"
def fetch_news(keywords):
    out=[]
    for kw in keywords:
        url=GDELT.format(q=kw.replace(" ","+"))
        try:
            r=requests.get(url, timeout=30)
            if r.status_code!=200: continue
            for a in r.json().get("articles",[]):
                out.append({"source":"GDELT","title":a.get("title",""),"url":a.get("url",""),"seendate":a.get("seendate",""),"domain":a.get("domain",""),"keyword":kw})
        except Exception: pass
        time.sleep(0.4)
    return out
