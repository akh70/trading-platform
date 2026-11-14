"""Policy rates and 2-year government yields for the platform's Rates tab (standard library only).

Writes data/rates-data.json: {"built": ..., "series": {ECON: {"pol": [[date, value], ...], "y2": [...]}}, "src": {...}}
A source that fails keeps its previous data; the summary reports what changed.
"""
import csv, io, json, os, re, time, traceback, zipfile, datetime as dt, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "rates-data.json")
START = "2020-09-01"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def get(url, timeout=90, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            err = e
            time.sleep(10 * (i + 1))
    raise err


def text(url):
    return get(url).decode("utf-8-sig", "replace")


def fnum(s):
    try:
        return round(float(s), 4)
    except (TypeError, ValueError):
        return None


def keep(rows):
    out = {}
    for d, v in rows:
        if v is not None and d >= START:
            out[d] = v
    return [[d, out[d]] for d in sorted(out)]


def fred(sid):
    t = text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}")
    return keep((l.split(",")[0], fnum(l.split(",")[1])) for l in t.strip().splitlines()[1:] if "," in l)


def macro(sid):
    """FRED series already downloaded by update_data.update_macro (avoids a second burst of FRED requests)."""
    m = json.load(open(os.path.join(ROOT, "data", "macro-data.json")))["series"]
    return keep((d, round(float(v), 4)) for d, v in m[sid])


def ecb(key):
    t = text(f"https://data-api.ecb.europa.eu/service/data/{key}?format=csvdata&startPeriod={START}&detail=dataonly")
    rd = csv.DictReader(io.StringIO(t))
    return keep((r["TIME_PERIOD"], fnum(r["OBS_VALUE"])) for r in rd)


def boe_iadb(code):
    d0 = dt.date.fromisoformat(START).strftime("%d/%b/%Y")
    t = text(f"https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={d0}&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
    rows = []
    for l in t.strip().splitlines()[1:]:
        p = l.split(",")
        try:
            rows.append((dt.datetime.strptime(p[0].strip(), "%d %b %Y").date().isoformat(), fnum(p[1])))
        except (ValueError, IndexError):
            pass
    return keep(rows)


def xlsx_rows(blob, *hints):
    """Rows (dict column -> cell string) of the first sheet whose name contains every hint."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    names = [s.get("name") for s in wb.find("m:sheets", NS)]
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = {r.get("Id"): r.get("Target") for r in rels}
    sheets = wb.find("m:sheets", NS)
    tgt = None
    for s in sheets:
        if all(h in s.get("name").lower() for h in hints):
            tgt = rid[s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            break
    if not tgt:
        raise ValueError(f"no sheet with {hints}: {names}")
    tgt = tgt.lstrip("/")
    tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    out = []
    for r in ET.fromstring(z.read(tgt)).find("m:sheetData", NS).findall("m:row", NS):
        row = {}
        for c in r.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find("m:v", NS)
            row[col] = "" if v is None else (ss[int(v.text)] if c.get("t") == "s" else v.text)
        out.append(row)
    return out


def boe_glc_2y(blob):
    """UK nominal spot 2-year (24 months) from a Bank of England GLC workbook."""
    rows = xlsx_rows(blob, "spot", "short")
    head = next((r for r in rows if r.get("A", "").strip().lower().startswith("months")), None)
    if head is None:
        raise ValueError("no 'months' header row")
    col = None
    for k, v in head.items():
        try:
            if abs(float(v) - 24) < 1e-9:
                col = k
        except ValueError:
            pass
    if col is None:
        raise ValueError(f"no 24-month column; header: {list(head.values())[:12]}")
    res = []
    for r in rows:
        a, v = r.get("A", ""), r.get(col, "")
        try:
            d = (dt.date(1899, 12, 30) + dt.timedelta(days=int(float(a)))).isoformat()
        except ValueError:
            continue
        res.append((d, fnum(v)))
    return res


def uk_2y(prev):
    base = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
    rows = []
    month_start = dt.date.today().replace(day=1).isoformat()
    if not prev or prev[-1][0] < (dt.date.fromisoformat(month_start) - dt.timedelta(days=7)).isoformat():
        z = zipfile.ZipFile(io.BytesIO(get(base + "glcnominalddata.zip", timeout=300)))
        for n in z.namelist():
            m = re.search(r"(\d{4}) to (present|\d{4})", n)
            if m and (m.group(2) == "present" or int(m.group(2)) >= 2020):
                rows += boe_glc_2y(z.read(n))
    else:
        rows += [tuple(x) for x in prev]
    z = zipfile.ZipFile(io.BytesIO(get(base + "latest-yield-curve-data.zip")))
    n = next(x for x in z.namelist() if "Nominal" in x)
    rows += boe_glc_2y(z.read(n))
    return keep(rows)


def boc():
    t = text(f"https://www.bankofcanada.ca/valet/observations/V39079,BD.CDN.2YR.DQ.YLD/csv?start_date={START}")
    body = t.split('"OBSERVATIONS"', 1)[1].strip().splitlines()
    rd = csv.reader(body)
    head = next(rd)
    i_pol, i_y2 = head.index("V39079"), head.index("BD.CDN.2YR.DQ.YLD")
    pol, y2 = [], []
    for r in rd:
        if len(r) > max(i_pol, i_y2):
            pol.append((r[0], fnum(r[i_pol])))
            y2.append((r[0], fnum(r[i_y2])))
    return keep(pol), keep(y2)


def rba(table, title, fmt):
    t = text(f"https://www.rba.gov.au/statistics/tables/csv/{table}-data.csv")
    rows = list(csv.reader(io.StringIO(t)))
    titles = next(r for r in rows if r and r[0] == "Title")
    i = [x.strip() for x in titles].index(title)
    out = []
    for r in rows:
        if len(r) > i:
            try:
                out.append((dt.datetime.strptime(r[0], fmt).date().isoformat(), fnum(r[i])))
            except ValueError:
                pass
    return keep(out)


def mof_2y():
    rows = []
    for u in ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
              "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"):
        for r in csv.reader(io.StringIO(text(u))):
            if len(r) > 2:
                try:
                    y, m, d = (int(x) for x in r[0].split("/"))
                    rows.append((dt.date(y, m, d).isoformat(), fnum(r[2])))
                except ValueError:
                    pass
    return keep(rows)


def snb_policy():
    t = text("https://data.snb.ch/api/cube/snboffzisa/data/csv/en")
    rows = []
    for l in t.splitlines():
        p = [x.strip('"') for x in l.split(";")]
        if len(p) == 3 and p[1] == "LZ" and p[2]:
            rows.append((p[0] + "-01", fnum(p[2])))
    return keep(rows)


def main():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"series": {}}
    before = json.dumps(old.get("series", {}), sort_keys=True)
    S = json.loads(before)
    jobs = {
        ("US", "pol"): lambda: macro("DFEDTARU"), ("US", "y2"): lambda: macro("DGS2"),
        ("EU", "pol"): lambda: ecb("FM/D.U2.EUR.4F.KR.DFR.LEV"), ("EU", "y2"): lambda: ecb("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"),
        ("UK", "pol"): lambda: boe_iadb("IUDBEDR"), ("UK", "y2"): lambda: uk_2y(S.get("UK", {}).get("y2")),
        ("AU", "pol"): lambda: rba("f1", "Cash Rate Target", "%d-%b-%Y"), ("AU", "y2"): lambda: rba("f2", "Australian Government 2 year bond", "%d-%b-%Y"),
        ("JP", "pol"): lambda: macro("IRSTCI01JPM156N"), ("JP", "y2"): mof_2y,
        ("CH", "pol"): snb_policy,
    }
    ca = None
    report = {}
    for (e, k), fn in list(jobs.items()) + [(("CA", "pol"), None), (("CA", "y2"), None)]:
        try:
            if e == "CA":
                ca = ca or boc()
                rows = ca[0] if k == "pol" else ca[1]
            else:
                rows = fn()
            prev = S.get(e, {}).get(k, [])
            if len(rows) < max(5, len(prev) - 10) or (prev and rows[-1][0] < prev[-1][0]):
                raise ValueError(f"sanity check failed ({len(rows)} rows vs {len(prev)} before)")
            S.setdefault(e, {})[k] = rows
            report[f"{e}.{k}"] = rows[-1]
        except Exception as ex:
            report[f"{e}.{k}"] = f"FAILED: {ex!r}"
            traceback.print_exc()
        time.sleep(2)
    new = {"built": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z", "start": START, "series": S,
           "src": {"US": "FRED (DFEDTARU, DGS2)", "EU": "ECB (deposit facility rate; AAA euro-area 2y spot)",
                   "UK": "Bank of England (Bank Rate; GLC nominal spot 2y)", "CA": "Bank of Canada Valet (target rate; 2y benchmark)",
                   "AU": "RBA (F1 cash rate target, daily; F2 2y bond)", "JP": "FRED call rate, monthly; Ministry of Finance JGB 2y",
                   "CH": "SNB policy rate, monthly; no current 2y source", "NZ": "not available automatically"}}
    if json.dumps(S, sort_keys=True) != before or not os.path.exists(OUT):
        json.dump(new, open(OUT, "w"), separators=(",", ":"))
    for k, v in report.items():
        print("RATES", k, v)
    return all(not str(v).startswith("FAILED") for v in report.values())


if __name__ == "__main__":
    main()
