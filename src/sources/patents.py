import requests, time
PV="https://api.patentsview.org/patents/query?q={q}&f=[%22patent_number%22,%22patent_date%22,%22patent_title%22]&o={%22per_page%22:10,%22page%22:1,%22order%22:-patent_date}"
def fetch_patents(keywords):
    out=[]
    for kw in keywords:
        q='{"_text_any":{"patent_title":"%s"}}'%kw
        url=PV.format(q=q)
        try:
            r=requests.get(url, timeout=30)
            if r.status_code!=200: continue
            for p in r.json().get("patents",[]):
                out.append({"source":"PatentsView","title":p.get("patent_title",""),"number":p.get("patent_number",""),"date":p.get("patent_date",""),"keyword":kw})
        except Exception: pass
        time.sleep(0.5)
    return out
