"""One-off check of official economic data sources (status, size, first bytes). Not used by the platform."""
import urllib.request, json, sys
UA={"User-Agent":"Mozilla/5.0 (compatible; trading-platform-probe/1.0)"}
P=[
("EUR HICP y/y (ECB)","https://data-api.ecb.europa.eu/service/data/ICP/M.U2.N.000000.4.ANR?format=csvdata&lastNObservations=2",None),
("EUR core HICP (ECB)","https://data-api.ecb.europa.eu/service/data/ICP/M.U2.N.XEF000.4.ANR?format=csvdata&lastNObservations=2",None),
("EUR unemployment (ECB)","https://data-api.ecb.europa.eu/service/data/LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T?format=csvdata&lastNObservations=2",None),
("EUR 2y AAA yield (ECB)","https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?format=csvdata&lastNObservations=2",None),
("UK CPI y/y (ONS)","https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data",None),
("UK unemployment (ONS)","https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms/data",None),
("UK wages (ONS)","https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms/data",None),
("UK Bank Rate (BoE)","https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Oct/2026&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N",None),
("CA CPI (StatCan)","https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods",[{"vectorId":41690973,"latestN":2}]),
("CA unemployment (StatCan)","https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods",[{"vectorId":2062815,"latestN":2}]),
("CA policy rate + 2y (BoC)","https://www.bankofcanada.ca/valet/observations/V39079,BD.CDN.2YR.DQ.YLD/json?recent=2",None),
("AU cash rate (RBA F1.1)","https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv",None),
("AU bond yields (RBA F2)","https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",None),
("AU inflation (RBA G1)","https://www.rba.gov.au/statistics/tables/csv/g1-data.csv",None),
("AU labour (RBA H5)","https://www.rba.gov.au/statistics/tables/csv/h5-data.csv",None),
("NZ yields (RBNZ B2 daily)","https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx",None),
("NZ OCR (RBNZ B2 monthly)","https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-monthly.xlsx",None),
("JP JGB yields (MoF)","https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",None),
("CH SNB cube list","https://data.snb.ch/api/cube/snboffzisa/data/csv/en",None),
("CH CPI (SNB plkoprinfla)","https://data.snb.ch/api/cube/plkoprinfla/data/csv/en",None),
("CH bond yields (SNB rendoblid)","https://data.snb.ch/api/cube/rendoblid/data/csv/en",None),
("US oil stocks (EIA WPSR)","https://ir.eia.gov/wpsr/table1.csv",None),
("US rig count (Baker Hughes)","https://rigcount.bakerhughes.com/na-rig-count",None),
]
for name,url,body in P:
    try:
        data=json.dumps(body).encode() if body else None
        h=dict(UA); 
        if body: h["Content-Type"]="application/json"
        with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h),timeout=45) as r:
            b=r.read(); ct=r.headers.get("Content-Type","")
            head=b[:260].decode("utf-8","replace").replace("\n"," | ") if "sheet" not in ct and not b[:2]==b"PK" else "(xlsx, %d bytes)"%len(b)
            tail=b[-200:].decode("utf-8","replace").replace("\n"," | ") if "sheet" not in ct and not b[:2]==b"PK" else ""
            print(f"OK   {name} [{r.status} {ct[:30]} {len(b)}B]\n     head: {head}\n     tail: {tail}")
    except Exception as e:
        print(f"FAIL {name}: {e}")
