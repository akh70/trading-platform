import csv, io, json, re, time, urllib.request
UA={"User-Agent":"Mozilla/5.0 (compatible; trading-platform-data/1.0; +https://github.com/akh70/trading-platform)"}
def get(u,timeout=60):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=timeout) as r: return r.read().decode("utf-8-sig","replace")
def rep(tag,fn):
    try: print("OK ",tag,fn(),flush=True)
    except Exception as e: print("ERR",tag,type(e).__name__,str(e)[:150],flush=True)
def fred(s):
    t=get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}&cosd=2025-06-01").strip().splitlines()
    v=[l for l in t[1:] if not l.endswith(",.")]; return len(v),v[-2:]
for s in "CPIAUCSL CPILFESL PCEPILFE PAYEMS UNRATE CES0500000003 ICSA RSAFS GDPC1 JTSJOL T5YIFR DCOILWTICO DFII10 T10YIE NFCI INDPRO".split():
    rep("FRED "+s,lambda s=s:fred(s)); time.sleep(1)
def esat(ds,q):
    j=json.loads(get(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{ds}?{q}&sinceTimePeriod=2025-06"))
    ix=j["dimension"]["time"]["category"]["index"]; inv={v:k for k,v in ix.items()}; vals=j["value"]
    ks=sorted(int(k) for k in vals); return j.get("label","")[:60],[(inv.get(k%len(ix)),vals[str(k)]) for k in ks[-3:]],list(j["dimension"].keys())
for ds,q in [("prc_hicp_manr","geo=EA&coicop=CP00"),("prc_hicp_manr","geo=EA&coicop=TOT_X_NRG_FOOD"),("prc_hicp_manr","geo=EA&coicop=SERV"),("prc_hicp_manr","geo=EA&coicop=NRG"),
             ("prc_hicp_minr","geo=EA&coicop18=TOTAL"),("prc_hicp_manr","geo=EA20&coicop=CP00"),("prc_hicp_fl","geo=EA"),("une_rt_m","geo=EA20&s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT"),
             ("sts_inpr_m","geo=DE&s_adj=SCA&nace_r2=B-D&unit=I21"),("namq_10_gdp","geo=EA20&unit=CLV_PCH_PRE&s_adj=SCA&na_item=B1GQ")]:
    rep(f"ESTAT {ds} {q}",lambda ds=ds,q=q:esat(ds,q))
def ons(path):
    j=json.loads(get("https://www.ons.gov.uk/"+path+"/data")); m=j.get("months") or j.get("quarters")
    return j["description"]["title"][:70],m[-1]["date"],m[-1]["value"]
for p in ["economy/inflationandpriceindices/timeseries/d7g7/mm23","economy/inflationandpriceindices/timeseries/dko8/mm23","economy/inflationandpriceindices/timeseries/d7nn/mm23",
          "employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms","employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/lms",
          "employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kaj4/lms","employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai7/lms",
          "economy/grossdomesticproductgdp/timeseries/ihyq/pn2","economy/grossdomesticproductgdp/timeseries/ecy2/mgdp","businessindustryandtrade/retailindustry/timeseries/j5ek/drsi"]:
    rep("ONS "+p.split("/")[-2],lambda p=p:ons(p))
def rba(t):
    rows=list(csv.reader(io.StringIO(get(f"https://www.rba.gov.au/statistics/tables/csv/{t}-data.csv"))))
    return [r[:4] for r in rows[:12]],[r[:4] for r in rows if r and re.match(r"\d\d/",r[0])][-2:]
for t in ["g1","h5","i2"]: rep("RBA "+t,lambda t=t:rba(t))
rep("BOJ",lambda:get("https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=json&lang=en&db=CO&code=TK99F1000601GCQ01000")[:700])
def snbh(c): 
    t=get(f"https://data.snb.ch/api/cube/{c}/data/csv/en").splitlines(); last=t[-1].split(";")[0]; return [l for l in t if l.startswith(last)][:20]
for c in ["amarbma","plkoprinfla","gdpap"]: rep("SNB "+c,lambda c=c:snbh(c))
rep("SNB dims amarbma",lambda:get("https://data.snb.ch/api/cube/amarbma/dimensions/en")[:900])
rep("SNB dims plkoprinfla",lambda:get("https://data.snb.ch/api/cube/plkoprinfla/dimensions/en")[:900])
