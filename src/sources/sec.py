import requests
from src.config import CIK, SEC_USER_AGENT
BASE="https://data.sec.gov/submissions/CIK{cik}.json"
def fetch_sec_filings():
    headers={"User-Agent":SEC_USER_AGENT}; items=[]
    for ticker,cik in CIK.items():
        cik10=str(cik).zfill(10); url=BASE.format(cik=cik10)
        try:
            r=requests.get(url, headers=headers, timeout=30)
            if r.status_code!=200: continue
            j=r.json(); rec=j.get("filings",{}).get("recent",{})
            acc,forms,dates = rec.get("accessionNumber",[]), rec.get("form",[]), rec.get("filingDate",[])
            docs = rec.get("primaryDocument", [""]*len(acc))
            for i in range(min(len(acc),len(forms),len(dates))):
                items.append({"source":"SEC","ticker":ticker,"accession":acc[i],"form":forms[i],"filed":dates[i],"primaryDoc":docs[i]})
        except Exception: 
            continue
    return items
