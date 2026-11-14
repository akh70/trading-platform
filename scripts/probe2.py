import urllib.request, zipfile, io, re, xml.etree.ElementTree as ET
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36","Accept":"*/*","Accept-Language":"en-US,en;q=0.9"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=90) as r: return r.read()
NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
def xlsx_sheets(b):
    z=zipfile.ZipFile(io.BytesIO(b)); wb=ET.fromstring(z.read("xl/workbook.xml"))
    return z,[s.get("name") for s in wb.find("m:sheets",NS)]
for u in ["https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalddata.zip","https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip"]:
    try:
        b=get(u); z=zipfile.ZipFile(io.BytesIO(b)); names=[i.filename for i in z.infolist()]; print("== BoE",u.split('/')[-1],len(b),names[:12])
        n=[x for x in names if "Nominal" in x or "nominal" in x]
        if n:
            zz,sh=xlsx_sheets(z.read(n[-1])); print("   sheets of",n[-1],sh)
            ss=[ "".join(t.itertext()) for t in ET.fromstring(zz.read("xl/sharedStrings.xml")).findall("m:si",NS)] if "xl/sharedStrings.xml" in zz.namelist() else []
            # find spot curve sheet
            idx=[i for i,s in enumerate(sh) if "spot" in s.lower()]
            if idx:
                x=ET.fromstring(zz.read(f"xl/worksheets/sheet{idx[0]+1}.xml")); rows=x.find("m:sheetData",NS).findall("m:row",NS)
                def val(c):
                    v=c.find("m:v",NS); 
                    if v is None: return ""
                    return ss[int(v.text)] if c.get("t")=="s" else v.text
                for r in rows[:6]+rows[-2:]: print("   R",r.get("r"),[val(c) for c in r.findall("m:c",NS)][:8])
    except Exception as e: print("== FAIL BoE",u,e)
for u in ["https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx"]:
    try: b=get(u); print("== RBNZ ok",len(b))
    except Exception as e: print("== FAIL RBNZ xlsx",e)
for cube in ["snboffzisa","rendoblim","rendeidglim","rendopar","zikreidglim"]:
    try:
        t=get(f"https://data.snb.ch/api/cube/{cube}/data/csv/en").decode("utf-8-sig","replace").splitlines()
        lz=[l for l in t if '"LZ"' in l][-2:] if cube=="snboffzisa" else []
        print("== SNB",cube,len(t),t[0][:80],t[1][:80] if len(t)>1 else "", "| last:",t[-1][:80],"| LZ:",lz)
    except Exception as e: print("== FAIL SNB",cube,e)
t=get("https://www.rba.gov.au/statistics/tables/csv/f2-data.csv").decode("utf-8-sig","replace").splitlines()
print("== RBA F2 rows", [l[:90] for l in t[6:12]], [l[:90] for l in t if l.startswith("12-Nov-2026") or l.startswith("13-Nov-2026")])
t=get("https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv").decode("utf-8-sig","replace").splitlines()
print("== RBA F1.1 rows", [l[:80] for l in t[6:12]], [l[:60] for l in t if l.endswith("2026") or "/2026" in l][-3:])
