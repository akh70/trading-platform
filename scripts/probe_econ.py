import csv, io, json, re, time, urllib.request
UA={"User-Agent":"Mozilla/5.0 (compatible; trading-platform-data/1.0; +https://github.com/akh70/trading-platform)"}
def get(u,timeout=60):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=timeout) as r: return r.read().decode("utf-8-sig","replace")
def rep(tag,fn):
    try: print("OK ",tag,json.dumps(fn(),ensure_ascii=False)[:5000].replace("\n"," "),flush=True)
    except Exception as e: print("ERR",tag,type(e).__name__,str(e)[:150],flush=True)
def esd():
    j=json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?geo=EA&unit=RCH_A&sinceTimePeriod=2026-09"))
    lab=j["dimension"]["coicop18"]["category"]["label"]; return [(k,v) for k,v in lab.items() if not re.match(r"CP\d",k)]
rep("ESTAT special aggs",esd)
rep("BOJ CO code",lambda:json.loads(get("https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=json&lang=en&db=CO&code=TK99F1000601GCQ01000")))
rep("BOJ meta CO",lambda:json.loads(get("https://www.stat-search.boj.or.jp/api/v1/getMetadata?format=json&lang=en&db=CO")))
def rba(t):
    rows=list(csv.reader(io.StringIO(get(f"https://www.rba.gov.au/statistics/tables/csv/{t}-data.csv"))))
    sid=next(r for r in rows if r and r[0]=="Series ID"); data=[r for r in rows if r and re.match(r"\d\d",r[0])]
    return sid[:6],data[-2][:4],data[-1][:4]
rep("RBA f1",lambda:rba("f1"))
