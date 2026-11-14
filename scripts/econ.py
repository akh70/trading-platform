"""Economic drivers per currency for the platform's Economy tab (standard library only).

Writes data/econ-data.json: {"built": ..., "series": {ID: {"f": freq, "u": unit, "src": source, "d": [[date, value], ...]}}}
Dates are period starts (YYYY-MM-DD). Values are already transformed (y/y %, m/m %, change, level).
A series that fails keeps its previous data. Only free official sources; licensed data (PMI, ISM, UMich, VIX) is never stored here.
"""
import csv, io, json, os, re, time, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "econ-data.json")
FROM = "2019-09-01"   # 12 months before the platform's history so y/y starts in 2020-09
KEEP = "2020-09-01"
UA = {"User-Agent": "Mozilla/5.0 (compatible; trading-platform-data/1.0; +https://github.com/akh70/trading-platform)"}


def get(url, data=None, headers=None, timeout=90, tries=3):
    err = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(rq, timeout=timeout) as r:
                return r.read().decode("utf-8-sig", "replace")
        except Exception as e:
            err = e
            time.sleep(6 * (i + 1))
    raise err


def f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def mdate(s):
    """Normalise '2026-09', '2026 SEP', '2026-Q3', '2026 Q3', '30/09/2026', '2026-09-01' to a period-start ISO date."""
    s = s.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return s + "-01"
    m = re.match(r"^(\d{4})[- ]?Q([1-4])$", s)
    if m:
        return "%s-%02d-01" % (m.group(1), 3 * int(m.group(2)) - 2)
    m = re.match(r"^(\d{4}) ([A-Z]{3})$", s)
    if m:
        return "%s-%02d-01" % (m.group(1), dt.datetime.strptime(m.group(2), "%b").month)
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return "%s-%s-01" % (m.group(3), m.group(2))
    raise ValueError(s)


# ---------- sources: each returns [(iso_date, value)] sorted ----------
def fred(sid):
    t = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={FROM}")
    return [(p[0], f(p[1])) for p in (l.split(",") for l in t.strip().splitlines()[1:]) if len(p) == 2 and f(p[1]) is not None]


def ecb(key):
    t = get(f"https://data-api.ecb.europa.eu/service/data/{key}?format=csvdata&startPeriod={FROM[:7]}&detail=dataonly")
    return [(mdate(r["TIME_PERIOD"]), f(r["OBS_VALUE"])) for r in csv.DictReader(io.StringIO(t)) if f(r["OBS_VALUE"]) is not None]


def estat(ds, q):
    j = json.loads(get(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{ds}?{q}&sinceTimePeriod={FROM[:7]}"))
    ix = j["dimension"]["time"]["category"]["index"]
    inv = {v: k for k, v in ix.items()}
    n = len(ix)
    out = [(mdate(inv[int(k) % n]), f(v)) for k, v in j["value"].items()]
    return sorted((d, v) for d, v in out if v is not None)


def ons(path):
    j = json.loads(get("https://www.ons.gov.uk/" + path + "/data"))
    rows = j.get("months") or j.get("quarters") or []
    return [(mdate(r["date"]), f(r["value"])) for r in rows if f(r["value"]) is not None and mdate(r["date"]) >= FROM]


def statcan(vec, n=90):
    b = json.dumps([{"vectorId": vec, "latestN": n}]).encode()
    j = json.loads(get("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods", data=b,
                       headers={"Content-Type": "application/json"}))
    return [(p["refPer"], f(p["value"])) for p in j[0]["object"]["vectorDataPoint"] if f(p["value"]) is not None]


def valet(sid):
    j = json.loads(get(f"https://www.bankofcanada.ca/valet/observations/{sid}/json?start_date={FROM}"))
    return [(o["d"], f(o[sid]["v"])) for o in j["observations"] if sid in o and f(o[sid]["v"]) is not None]


_rba = {}
def rba(table, sid):
    if table not in _rba:
        _rba[table] = list(csv.reader(io.StringIO(get(f"https://www.rba.gov.au/statistics/tables/csv/{table}-data.csv"))))
    rows = _rba[table]
    ids = next(r for r in rows if r and r[0] == "Series ID")
    i = ids.index(sid)
    out = []
    for r in rows:
        if r and re.match(r"^\d{2}/\d{2}/\d{4}$", r[0]) and len(r) > i and f(r[i]) is not None:
            out.append((mdate(r[0]), f(r[i])))
    return [x for x in out if x[0] >= FROM]


_snb = {}
def snb(cube, code):
    if cube not in _snb:
        _snb[cube] = get(f"https://data.snb.ch/api/cube/{cube}/data/csv/en").splitlines()
    out = []
    for l in _snb[cube]:
        p = [x.strip('"') for x in l.split(";")]
        if len(p) == 3 and p[1] == code and f(p[2]) is not None:
            out.append((mdate(p[0]), f(p[2])))
    return [x for x in out if x[0] >= FROM]


def boj(db, code):
    j = json.loads(get(f"https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=json&lang=en&db={db}&code={code}"))
    v = j["RESULTSET"][0]["VALUES"]
    out = []
    for d, x in zip(v["SURVEY_DATES"], v["VALUES"]):
        d = str(d)
        if len(d) == 6 and f(x) is not None:   # YYYYQQ for quarterly
            y, q = int(d[:4]), int(d[4:])
            out.append(("%d-%02d-01" % (y, 3 * q - 2), f(x)))
    return [x for x in out if x[0] >= FROM]


def mof(col):
    rows = []
    for u in ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
              "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"):
        rd = list(csv.reader(io.StringIO(get(u))))
        head = next(r for r in rd if r and r[0].strip() == "Date")
        i = [h.strip() for h in head].index(col)
        for r in rd:
            if len(r) > i and f(r[i]) is not None:
                try:
                    y, m, d = (int(x) for x in r[0].split("/"))
                    rows.append((dt.date(y, m, d).isoformat(), f(r[i])))
                except ValueError:
                    pass
    return sorted(dict(rows).items())


# ---------- transforms ----------
def by_period(rows):
    return dict(rows)


def shift(d, months):
    y, m = int(d[:4]), int(d[5:7]) + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return "%04d-%02d-01" % (y, m)


def yy(rows, step=12):
    """Year-over-year % change; step 12 for monthly, 4 for quarterly (in periods, matched by calendar)."""
    mp = by_period(rows)
    months = 12
    return [(d, round((v / mp[shift(d, -months)] - 1) * 100, 2)) for d, v in rows if shift(d, -months) in mp and mp[shift(d, -months)]]


def pp(rows, months=1, ann=False):
    mp = by_period(rows)
    out = []
    for d, v in rows:
        b = mp.get(shift(d, -months))
        if b:
            r = v / b
            out.append((d, round(((r ** (12 / months) - 1) if ann else (r - 1)) * 100, 2)))
    return out


def diff(rows, months=1, scale=1.0):
    mp = by_period(rows)
    return [(d, round((v - mp[shift(d, -months)]) * scale, 1)) for d, v in rows if shift(d, -months) in mp]


def weekly(rows, scale=1.0, ma=1):
    """Daily/weekly -> one value per ISO week (last obs), optional moving average of ma weeks."""
    wk = {}
    for d, v in rows:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        wk[(y, w)] = (d, v)
    vals = [wk[k] for k in sorted(wk)]
    out = []
    for i, (d, v) in enumerate(vals):
        if i + 1 >= ma:
            out.append((d, round(sum(x[1] for x in vals[i - ma + 1:i + 1]) / ma * scale, 3)))
    return out


def lvl(rows, scale=1.0, nd=3):
    return [(d, round(v * scale, nd)) for d, v in rows]


# ---------- the series the Economy tab uses ----------
def it_de_spread():
    it, de = dict(ecb("IRS/M.IT.L.L40.CI.0000.EUR.N.Z")), dict(ecb("IRS/M.DE.L.L40.CI.0000.EUR.N.Z"))
    return [(d, round((it[d] - de[d]) * 100)) for d in sorted(it) if d in de]


def eu_hicp(code):
    """ECOICOP v2 dataset (2026 onwards, with back data); falls back to the frozen ECOICOP v1 dataset for older months."""
    new = estat("prc_hicp_minr", f"geo=EA&unit=RCH_A&coicop18={code}")
    old_code = {"TOTAL": "CP00"}.get(code, code)
    try:
        old = estat("prc_hicp_manr", f"geo=EA&coicop={old_code}")
    except Exception:
        old = []
    m = dict(old)
    m.update(dict(new))
    return sorted(m.items())


S = {
    # United States (FRED, BLS/BEA/DoL data)
    "US_CORE_MM": ("m", "%", "BLS via FRED CPILFESL", lambda: pp(fred("CPILFESL"))),
    "US_CORE_YY": ("m", "%", "BLS via FRED CPILFESL", lambda: yy(fred("CPILFESL"))),
    "US_CPI_YY": ("m", "%", "BLS via FRED CPIAUCSL", lambda: yy(fred("CPIAUCSL"))),
    "US_PCEC_YY": ("m", "%", "BEA via FRED PCEPILFE", lambda: yy(fred("PCEPILFE"))),
    "US_NFP": ("m", "k", "BLS via FRED PAYEMS", lambda: diff(fred("PAYEMS"))),
    "US_UR": ("m", "%", "BLS via FRED UNRATE", lambda: lvl(fred("UNRATE"))),
    "US_AHE_YY": ("m", "%", "BLS via FRED CES0500000003", lambda: yy(fred("CES0500000003"))),
    "US_CLAIMS": ("w", "k", "DoL via FRED ICSA (4-week avg)", lambda: weekly(fred("ICSA"), 0.001, 4)),
    "US_JOLTS": ("m", "m", "BLS via FRED JTSJOL", lambda: lvl(fred("JTSJOL"), 0.001)),
    "US_RETAIL_MM": ("m", "%", "Census via FRED RSAFS", lambda: pp(fred("RSAFS"))),
    "US_GDP_QA": ("q", "%", "BEA via FRED GDPC1 (q/q annualised)", lambda: pp(fred("GDPC1"), 3, ann=True)),
    "US_IP_YY": ("m", "%", "Fed via FRED INDPRO", lambda: yy(fred("INDPRO"))),
    "US_5Y5Y": ("w", "%", "FRED T5YIFR", lambda: weekly(fred("T5YIFR"))),
    "US_REAL10": ("w", "%", "FRED DFII10", lambda: weekly(fred("DFII10"))),
    "US_BE10": ("w", "%", "FRED T10YIE", lambda: weekly(fred("T10YIE"))),
    "US_NFCI": ("w", "", "Chicago Fed via FRED NFCI", lambda: weekly(fred("NFCI"))),
    "WTI": ("w", "$", "EIA via FRED DCOILWTICO", lambda: weekly(fred("DCOILWTICO"))),
    # Euro area (Eurostat, ECB)
    "EU_HICP_YY": ("m", "%", "Eurostat prc_hicp_minr TOTAL", lambda: eu_hicp("TOTAL")),
    "EU_CORE_YY": ("m", "%", "Eurostat prc_hicp_minr TOT_X_NRG_FOOD", lambda: eu_hicp("TOT_X_NRG_FOOD")),
    "EU_SERV_YY": ("m", "%", "Eurostat prc_hicp_minr SERV", lambda: eu_hicp("SERV")),
    "EU_NRG_YY": ("m", "%", "Eurostat prc_hicp_minr NRG", lambda: eu_hicp("NRG")),
    "EU_UR": ("m", "%", "ECB LFSI", lambda: lvl(ecb("LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T"), 1, 2)),
    "EU_GDP_QQ": ("q", "%", "Eurostat namq_10_gdp", lambda: estat("namq_10_gdp", "geo=EA20&unit=CLV_PCH_PRE&s_adj=SCA&na_item=B1GQ")),
    "EU_WAGES_YY": ("q", "%", "ECB negotiated wages STS INWR", lambda: lvl(ecb("STS/Q.I9.N.INWR.000000.3.ANR"), 1, 2)),
    "EU_DE_IP_YY": ("m", "%", "Eurostat sts_inpr_m DE", lambda: yy(estat("sts_inpr_m", "geo=DE&s_adj=SCA&nace_r2=B-D&unit=I21"))),
    "EU_IT_DE": ("m", "bp", "ECB IRS 10y IT minus DE", it_de_spread),
    "EU_M3_YY": ("m", "%", "ECB BSI M3", lambda: lvl(ecb("BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A"), 1, 2)),
    # United Kingdom (ONS)
    "UK_CPI_YY": ("m", "%", "ONS D7G7", lambda: ons("economy/inflationandpriceindices/timeseries/d7g7/mm23")),
    "UK_CORE_YY": ("m", "%", "ONS DKO8", lambda: ons("economy/inflationandpriceindices/timeseries/dko8/mm23")),
    "UK_SERV_YY": ("m", "%", "ONS D7NN", lambda: ons("economy/inflationandpriceindices/timeseries/d7nn/mm23")),
    "UK_UR": ("m", "%", "ONS MGSX", lambda: ons("employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms")),
    "UK_PAY_YY": ("m", "%", "ONS KAI9 (regular pay, 3m y/y)", lambda: ons("employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/lms")),
    "UK_PRIVPAY_YY": ("m", "%", "ONS KAJ4 (private regular pay, 3m y/y)", lambda: ons("employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kaj4/lms")),
    "UK_GDP_QQ": ("q", "%", "ONS IHYQ", lambda: ons("economy/grossdomesticproductgdp/timeseries/ihyq/pn2")),
    "UK_GDP_MM": ("m", "%", "ONS ECY2 (monthly GDP)", lambda: pp(ons("economy/grossdomesticproductgdp/timeseries/ecy2/mgdp"))),
    "UK_RETAIL_YY": ("m", "%", "ONS J5EK", lambda: yy(ons("businessindustryandtrade/retailindustry/timeseries/j5ek/drsi"))),
    # Canada (Statistics Canada, Bank of Canada)
    "CA_CPI_YY": ("m", "%", "StatCan v41690973", lambda: yy(statcan(41690973))),
    "CA_TRIM": ("m", "%", "Bank of Canada CPI-trim", lambda: lvl(valet("CPI_TRIM"), 1, 2)),
    "CA_MEDIAN": ("m", "%", "Bank of Canada CPI-median", lambda: lvl(valet("CPI_MEDIAN"), 1, 2)),
    "CA_UR": ("m", "%", "StatCan v2062815", lambda: lvl(statcan(2062815), 1, 2)),
    "CA_EMP": ("m", "k", "StatCan v2062811 (monthly change)", lambda: diff(statcan(2062811))),
    "CA_GDP_MM": ("m", "%", "StatCan v65201210", lambda: pp(statcan(65201210))),
    "CA_BCPI_ENER": ("m", "", "Bank of Canada BCPI energy", lambda: lvl(valet("M.ENER"), 1, 1)),
    # Australia (RBA tables, ABS data)
    "AU_CPI_YY": ("q", "%", "RBA G1 GCPIAGYP", lambda: rba("g1", "GCPIAGYP")),
    "AU_TRIM_YY": ("q", "%", "RBA G1 trimmed mean", lambda: rba("g1", "GCPIOCPMTMYP")),
    "AU_UR": ("m", "%", "RBA H5 GLFSURSA", lambda: rba("h5", "GLFSURSA")),
    "AU_EMP_YY": ("m", "%", "RBA H5 GLFSEPTSYP", lambda: rba("h5", "GLFSEPTSYP")),
    "AU_COMM_YY": ("m", "%", "RBA I2 commodity prices US$", lambda: yy(rba("i2", "GRCPAIUSD"))),
    "AU_BULK_YY": ("m", "%", "RBA I2 bulk spot (iron ore, coal, LNG) US$", lambda: yy(rba("i2", "GRCPBCSUSD"))),
    # Switzerland (SNB)
    "CH_CPI_YY": ("m", "%", "SFSO via SNB plkoprinfla TLK", lambda: snb("plkoprinfla", "TLK")),
    "CH_CORE_YY": ("m", "%", "SNB trimmed mean (plkoprinfla KGM)", lambda: snb("plkoprinfla", "KGM")),
    "CH_UR": ("m", "%", "SECO via SNB amarbma S1", lambda: snb("amarbma", "S1")),
    # Japan (BoJ, MoF)
    "JP_TANKAN_LM": ("q", "pt", "BoJ Tankan large manufacturers DI", lambda: boj("CO", "TK99F1000601GCQ01000")),
    "JP_TANKAN_LN": ("q", "pt", "BoJ Tankan large non-manufacturers DI", lambda: boj("CO", "TK99F2000601GCQ01000")),
    "JP_10Y": ("w", "%", "MoF JGB 10y", lambda: weekly(mof("10Y"))),
}


def main():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"series": {}}
    ser = old.get("series", {})
    before = json.dumps(ser, sort_keys=True)
    ok, bad = [], []
    for sid, (fq, unit, src, fn) in S.items():
        try:
            rows = [(d, v) for d, v in fn() if d >= KEEP]
            prev = ser.get(sid, {}).get("d", [])
            if not rows or (prev and rows[-1][0] < prev[-1][0]) or len(rows) < len(prev) - 6:
                raise ValueError("sanity check failed (%d rows)" % len(rows))
            ser[sid] = {"f": fq, "u": unit, "src": src, "d": [[d, v] for d, v in rows]}
            ok.append(sid)
            print("ECON", sid, rows[-1])
        except Exception as e:
            bad.append(sid)
            print("ECON", sid, "FAILED, keeping previous:", type(e).__name__, str(e)[:120])
        time.sleep(0.5)
    if json.dumps(ser, sort_keys=True) != before:
        out = {"built": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z", "series": ser,
               "note": "Official free sources only. Values are transformed (see each src)."}
        json.dump(out, open(OUT, "w"), separators=(",", ":"))
        print("ECON: wrote", len(ser), "series")
    print("ECON summary: ok", len(ok), "failed", len(bad), bad)
    return bad


if __name__ == "__main__":
    main()
