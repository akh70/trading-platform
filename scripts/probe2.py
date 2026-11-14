import urllib.request, zipfile, io, re
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36","Accept":"*/*"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60) as r: return r.read()
def show(name,u,n=8,tail=4,grep=None):
    try:
        b=get(u); t=b.decode("utf-8-sig","replace"); L=t.splitlines()
        print(f"== {name}: {len(b)}B {len(L)} lines")
        for l in L[:n]: print("  H|",l[:220])
        if grep:
            g=[l for l in L if re.search(grep,l)]; print("  grep",len(g)); [print("  G|",l[:220]) for l in g[:6]+g[-3:]]
        for l in L[-tail:]: print("  T|",l[:220])
    except Exception as e: print("== FAIL",name,e)
show("MoF all","https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",4,3)
show("MoF cur","https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",3,2)
show("RBA F2","https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",12,3)
show("RBA F1.1","https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv",12,2)
show("SNB policy snboffzisa","https://data.snb.ch/api/cube/snboffzisa/data/csv/en",8,4)
show("SNB rendoblid","https://data.snb.ch/api/cube/rendoblid/data/csv/en",8,3,grep=r'"2026-10-3')
show("SNB zimoma","https://data.snb.ch/api/cube/zimoma/data/csv/en",8,4)
show("BoE IADB titles","https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Oct/2026&Dateto=now&SeriesCodes=IUDBEDR,IUDSNZC,IUDMNZC&CSVF=TT&UsingCodes=Y&VPD=Y&VFD=N",8,3)
try:
    b=get("https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip")
    z=zipfile.ZipFile(io.BytesIO(b)); print("== BoE yield zip",len(b),[ (i.filename,i.file_size) for i in z.infolist()])
except Exception as e: print("== FAIL BoE zip",e)
for u in ["https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx","https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"]:
    try: b=get(u); print("== RBNZ ok",u,len(b))
    except Exception as e: print("== FAIL RBNZ",u,e)
show("ECB 2y AAA hist","https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?format=csvdata&startPeriod=2020-09-01&detail=dataonly",3,2)
show("ECB DFR","https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&startPeriod=2026-09-01&detail=dataonly",3,2)
show("BoC hist","https://www.bankofcanada.ca/valet/observations/V39079,BD.CDN.2YR.DQ.YLD/csv?start_date=2026-10-25",12,3)
