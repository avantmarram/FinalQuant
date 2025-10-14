from datetime import datetime, timedelta

POS = ("beats","partnership","milestone","expands","award","win","funding","contract","approved","record")
NEG = ("delay","lawsuit","probe","guidance cut","miss","downgrade","terminate","reject","halt")

def _iso(dt):
    if isinstance(dt, datetime): return dt.isoformat()+"Z"
    try: return datetime.fromisoformat(str(dt)).isoformat()+"Z"
    except Exception: return datetime.utcnow().isoformat()+"Z"

def _sent(text: str) -> int:
    t = (text or "").lower()
    s = 0
    s += sum(k in t for k in POS)
    s -= sum(k in t for k in NEG)
    return s

def score_items(arxiv, sec, patents, news, prices):
    signals = []
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # map for price lookup
    price_map = {p["ticker"]: p for p in prices}

    # ---- SEC (dedup by accession) ----
    seen_acc = set()
    for f in sec:
        acc = f.get("accession") or f.get("accessionNumber")
        if acc in seen_acc: 
            continue
        seen_acc.add(acc)
        form = f.get("form","")
        filed = f.get("filed","")
        base = 6 if form in {"10-K","10-Q","8-K","S-1","6-K"} else 4
        # ekstra boost hvis fersk filing (innen 7 dager)
        try:
            is_recent = datetime.fromisoformat(filed) >= week_ago
        except Exception:
            is_recent = False
        score = base + (1 if is_recent else 0)
        signals.append({
            "type": "SEC_FILING",
            "ticker": f.get("ticker"),
            "form": form,
            "filed": filed,
            "score": score,
            "ts": _iso(filed or now),
        })

    # ---- Patents ----
    for p in patents:
        d = p.get("date") or ""
        score = 5
        try:
            if datetime.fromisoformat(d) >= week_ago:
                score += 1
        except Exception:
            pass
        signals.append({
            "type": "PATENT",
            "title": p.get("title",""),
            "date": d,
            "score": score,
            "ts": _iso(d or now),
        })

    # ---- arXiv ----
    for a in arxiv:
        title = a.get("title","")
        score = 3
        if any(k in title.lower() for k in ["fault","error","superconduct","ion","neutral atom","photonic"]):
            score += 2
        signals.append({
            "type": "ARXIV",
            "title": title,
            "published": a.get("published",""),
            "link": a.get("link",""),
            "score": score,
            "ts": _iso(a.get("published") or now),
        })

    # ---- News (med enkel sentiment) ----
    for n in news:
        title = n.get("title","")
        s = 3 + max(min(_sent(title), 2), -2)  # clamp [-2,+2]
        signals.append({
            "type": "NEWS",
            "title": title,
            "url": n.get("url",""),
            "seen": n.get("seendate",""),
            "score": s,
            "ts": _iso(n.get("seendate") or now),
        })

    # ---- Price spikes/dips ----
    for pr in prices:
        ch = pr.get("change_pct", 0) or 0
        if ch >= 15:
            signals.append({
                "type":"PRICE_SPIKE","ticker":pr.get("ticker"),
                "change_pct":ch,"score":8,"ts":_iso(pr.get("ts") or now)
            })
        elif ch <= -15:
            signals.append({
                "type":"PRICE_DIP","ticker":pr.get("ticker"),
                "change_pct":ch,"score":7,"ts":_iso(pr.get("ts") or now)
            })

    # ---- Kryss-boost: filing + spike samme uke, gi +1 ----
    recent = [s for s in signals if s.get("ts","") >= week_ago.isoformat()]
    recent_by_ticker = {}
    for s in recent:
        t = s.get("ticker") or "?"
        recent_by_ticker.setdefault(t, []).append(s)
    for bucket in recent_by_ticker.values():
        has_filing = any(s["type"]=="SEC_FILING" for s in bucket)
        has_spike  = any(s["type"]=="PRICE_SPIKE" for s in bucket)
        if has_filing and has_spike:
            for s in bucket:
                s["score"] += 1

    # sortér nyest først, så score
    signals.sort(key=lambda x: (x.get("ts",""), x.get("score",0)), reverse=True)
    return signals
