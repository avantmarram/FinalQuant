import os, json
from datetime import datetime
from src.config import (TICKERS, COMPANIES, ARXIV_QUERIES, NEWS_KEYWORDS, PATENT_KEYWORDS, DATA_JSON, SIGNALS_JSON, STATE_JSON)
from src.sources.arxiv import fetch_arxiv
from src.sources.sec import fetch_sec_filings
from src.sources.patents import fetch_patents
from src.sources.news import fetch_news
from src.sources.prices import fetch_prices
from src.logic.rules import score_items
from src.notifier import send_discord

def load_state():
    try:
        with open(STATE_JSON,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return {"notified_ids":[]}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
    with open(STATE_JSON,"w",encoding="utf-8") as f: json.dump(state,f,ensure_ascii=False,indent=2)

def main():
    arxiv=fetch_arxiv(ARXIV_QUERIES)
    sec=fetch_sec_filings()
    patents=fetch_patents(PATENT_KEYWORDS+COMPANIES)
    news=fetch_news(NEWS_KEYWORDS+COMPANIES)
    prices=fetch_prices(TICKERS)

    signals=score_items(arxiv,sec,patents,news,prices)

    data={"generated_at":datetime.utcnow().isoformat()+"Z","tickers":TICKERS,"prices":prices,
           "counts":{"arxiv":len(arxiv),"sec":len(sec),"patents":len(patents),"news":len(news),"signals":len(signals)}}

    os.makedirs("docs",exist_ok=True)
    with open(DATA_JSON,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
    with open(SIGNALS_JSON,"w",encoding="utf-8") as f: json.dump(signals[:200],f,ensure_ascii=False,indent=2)

    state=load_state(); notified=set(state.get("notified_ids",[])); new=[]
    for s in signals[:3]:
        sid=json.dumps(s,sort_keys=True)
        if sid not in notified:
            send_discord(f"**{s.get('type')}** • score {s.get('score')}\n{json.dumps(s,ensure_ascii=False)}")
            new.append(sid)
    if new:
        state["notified_ids"]=list(notified.union(new)); save_state(state)
    print("OK")

if __name__=="__main__":
    main()
