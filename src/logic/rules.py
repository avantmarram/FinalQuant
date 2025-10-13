from datetime import datetime
def score_items(arxiv, sec, patents, news, prices):
    signals=[]
    good_forms={"8-K","10-K","10-Q","S-1","6-K"}
    for f in sec:
        if f.get("form") in good_forms:
            signals.append({"type":"SEC_FILING","ticker":f.get("ticker"),"form":f.get("form"),"filed":f.get("filed"),"score":7})
    for p in patents:
        d=p.get("date"); recent=0
        try:
            if d:
                dt=datetime.fromisoformat(d); recent=1 if (datetime.utcnow()-dt).days<30 else 0
        except Exception: pass
        signals.append({"type":"PATENT","title":p.get("title",""),"date":d or "","score":5+recent})
    for a in arxiv:
        title=(a.get("title","") or "").lower(); score=3
        if any(k in title for k in ["fault","error","superconduct","ion","neutral atom"]): score+=2
        signals.append({"type":"ARXIV","title":a.get("title",""),"published":a.get("published",""),"link":a.get("link",""),"score":score})
    for n in news[:20]:
        signals.append({"type":"NEWS","title":n.get("title",""),"url":n.get("url",""),"seen":n.get("seendate",""),"score":3})
    for pr in prices:
        ch=pr.get("change_pct",0)
        if ch>=15: signals.append({"type":"PRICE_SPIKE","ticker":pr.get("ticker"),"change_pct":ch,"score":8})
        if ch<=-15: signals.append({"type":"PRICE_DIP","ticker":pr.get("ticker"),"change_pct":ch,"score":8})
    signals.sort(key=lambda x:x.get("score",0), reverse=True)
    return signals
