import csv, io, json, re, time, urllib.request
UA={"User-Agent":"Mozilla/5.0 (compatible; trading-platform-data/1.0; +https://github.com/akh70/trading-platform)"}
def get(u,timeout=60):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=timeout) as r: return r.read().decode("utf-8-sig","replace")
def rep(tag,fn):
    try: print("OK ",tag,fn(),flush=True)
    except Exception as e: print("ERR",tag,type(e).__name__,str(e)[:150],flush=True)
def esd(q):
    j=json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?"+q+"&sinceTimePeriod=2026-08"))
    d=j["dimension"]; return {k:list(d[k]["category"]["label"].items())[:80] for k in d if k!="time"}, j["size"], list(j["value"].items())[:12]
rep("ESTAT minr dims",lambda:esd("geo=EA"))
rep("ESTAT minr EA RCH_A",lambda:esd("geo=EA&unit=RCH_A&coicop18=TOTAL"))
for u in ["https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=json&lang=en&db=CO&code=TK99F1000601GCQ01000",
          "https://www.stat-search.boj.or.jp/api/v1/getMetadata?format=json&lang=en&db=PR01",
          "https://www.stat-search.boj.or.jp/api/v1/getMetadata?format=json&lang=en&db=CO"]:
    rep("BOJ "+u[-40:],lambda u=u:get(u)[:1500])
def rba(t):
    rows=list(csv.reader(io.StringIO(get(f"https://www.rba.gov.au/statistics/tables/csv/{t}-data.csv"))))
    ti=next(r for r in rows if r and r[0]=="Title"); sid=next(r for r in rows if r and r[0]=="Series ID")
    data=[r for r in rows if r and re.match(r"\d\d/",r[0])]
    out=[]
    for i in range(1,len(sid)):
        last=[(r[0],r[i]) for r in data if len(r)>i and r[i].strip()]
        out.append((sid[i],ti[i][:45],last[-1] if last else None))
    return out
for t in ["g1","h5","i2","f1.1"]: rep("RBA "+t,lambda t=t:rba(t))
