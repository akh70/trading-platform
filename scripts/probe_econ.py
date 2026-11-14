"""One-off probe: which official series answer from a GitHub runner. Prints status, count, last obs."""
import csv, io, json, re, sys, time, urllib.request
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0","Accept":"*/*"}
def get(u,data=None,h=None,timeout=60):
    rq=urllib.request.Request(u,data=data,headers={**UA,**(h or {})})
    with urllib.request.urlopen(rq,timeout=timeout) as r: return r.read().decode("utf-8-sig","replace")
def rep(tag,fn):
    try:
        r=fn(); print("OK ",tag,r,flush=True)
    except Exception as e: print("ERR",tag,type(e).__name__,str(e)[:120],flush=True)
def fred(s):
    t=get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}&cosd=2024-01-01").strip().splitlines()
    v=[l for l in t[1:] if not l.endswith(",.")]; return len(v),v[-1]
def ecb(k):
    t=get(f"https://data-api.ecb.europa.eu/service/data/{k}?format=csvdata&startPeriod=2024-01&detail=dataonly")
    r=list(csv.DictReader(io.StringIO(t))); return len(r),r[-1]["TIME_PERIOD"],r[-1]["OBS_VALUE"]
def ons(c,ds):
    j=json.loads(get(f"https://www.ons.gov.uk/economy/x/timeseries/{c.lower()}/{ds}/data"))
    m=j.get("months") or j.get("quarters"); return j["description"]["title"][:70],len(m),m[-1]["date"],m[-1]["value"]
for s in "CPIAUCSL CPILFESL PCEPILFE PAYEMS UNRATE CES0500000003 ICSA RSAFS INDPRO GDPC1 JTSJOL T5YIFR HOUST DCOILWTICO DFII10 T10YIE NFCI DTWEXBGS".split():
    rep("FRED "+s,lambda s=s:fred(s)); time.sleep(1)
for k in ["ICP/M.U2.N.000000.4.ANR","ICP/M.U2.N.XEF000.4.ANR","ICP/M.U2.N.SERV00.4.ANR","ICP/M.U2.N.NRGY00.4.ANR",
          "LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T","MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY","MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GQ",
          "STS/Q.I9.N.INWR.000000.3.ANR","IRS/M.IT.L.L40.CI.0000.EUR.N.Z","IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
          "BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A","STS/M.I9.Y.PROD.NS0020.4.000","STS/M.DE.Y.PROD.NS0020.4.000","ICP/M.DE.N.000000.4.ANR"]:
    rep("ECB "+k,lambda k=k:ecb(k))
for c,ds in [("D7G7","mm23"),("DKO8","mm23"),("D7NN","mm23"),("L55O","mm23"),("MGSX","lms"),("KAI9","lms"),("KAJ4","lms"),("KAI7","lms"),("KAJ5","lms"),("KAC4","lms"),("ECY2","mgdp"),("IHYQ","pn2"),("J5EK","drsi"),("ABMZ","pn2")]:
    rep("ONS "+c,lambda c=c,ds=ds:ons(c,ds))
def boc_list():
    j=json.loads(get("https://www.bankofcanada.ca/valet/lists/series/json"))["series"]
    return [(k,v["label"][:50]) for k,v in j.items() if re.search(r"CPI|cpi",k+v["label"])][:40]
rep("BOC list",boc_list)
def statcan(v):
    b=json.dumps([{"vectorId":v,"latestN":3}]).encode()
    j=json.loads(get("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods",data=b,h={"Content-Type":"application/json"}))
    p=j[0]["object"]["vectorDataPoint"]; return [(x["refPer"],x["value"]) for x in p]
for v in [2062815,41690973,41690914,65201210,1446859483,2062811]:
    rep(f"STATCAN v{v}",lambda v=v:statcan(v))
def rba_titles(t):
    rows=list(csv.reader(io.StringIO(get(f"https://www.rba.gov.au/statistics/tables/csv/{t}-data.csv"))))
    ti=next(r for r in rows if r and r[0]=="Title"); last=[r for r in rows if r and re.match(r"\d",r[0])][-1]
    return [(a,b) for a,b in zip(ti[1:],last[1:]) if a][:30], last[0]
for t in ["g1","g3","h5","i2","h3","d2"]:
    rep("RBA "+t,lambda t=t:rba_titles(t))
def snb(c):
    t=get(f"https://data.snb.ch/api/cube/{c}/data/csv/en").splitlines()
    return t[:3],len(t),t[-3:]
for c in ["plkopr","plkoprinfla","amarbma","rendoblim","rendoblid","gdpap","conretail"]:
    rep("SNB "+c,lambda c=c:snb(c))
rep("BOJ api",lambda:get("https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=json&lang=en&db=CO&code=TK99F1000601GCQ01000")[:300])
rep("ESTAT stat.go.jp",lambda:get("https://www.stat.go.jp/english/data/cpi/1581-z.html")[:200])
rep("RBNZ",lambda:get("https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx")[:50])
rep("StatsNZ",lambda:get("https://www.stats.govt.nz/indicators/consumers-price-index-cpi/")[:100])
