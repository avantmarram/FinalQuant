import feedparser, time
API="http://export.arxiv.org/api/query?search_query={q}&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending"
def fetch_arxiv(queries):
    out=[]
    for q in queries:
        url=API.format(q=q.replace(" ","+")); feed=feedparser.parse(url)
        for e in feed.entries[:10]:
            out.append({"source":"arXiv","title":e.get("title",""),"link":e.get("link",""),"published":e.get("published",""),"summary":e.get("summary","")[:500],"query":q})
        time.sleep(0.8)
    return out
