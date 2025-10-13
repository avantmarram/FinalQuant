import requests, time
PV="https://api.patentsview.org/patents/query?q={q}&f=['patent_number','patent_date','patent_title']&o={'per_page':10,'page':1,'order':'-patent_date'}"
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
