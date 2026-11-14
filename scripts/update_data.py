"""Weekly/daily data refresh for the platform (runs on GitHub Actions, standard library only).

- COT: appends any new weekly CFTC reports (financial, metals, petroleum; futures only) to data/cot-data.json.
  A week is added only when all 13 markets parse; otherwise nothing is written for that week.
- Macro: rewrites data/macro-data.json from FRED (WALCL, WTREGEN, RRPONTSYD, DGS2, DGS10) after sanity checks.
- Writes `stale=true` to $GITHUB_OUTPUT when the newest COT report is older than expected, so the run fails and notifies.
"""
import json, os, re, sys, html, time, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COT_F = os.path.join(ROOT, "data", "cot-data.json")
MAC_F = os.path.join(ROOT, "data", "macro-data.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; trading-platform-data/1.0; +https://github.com/akh70/trading-platform)"}
FIN = {"EUR": "099741", "GBP": "096742", "JPY": "097741", "CHF": "092741", "CAD": "090741", "AUD": "232741",
       "NZD": "112741", "DXY": "098662", "NQ": "209742", "BTC": "133741"}
DIS = {"other": {"XAU": "088691", "XAG": "084691"}, "petroleum": {"WTI": "067651"}}
ORDER = list(FIN) + ["XAU", "XAG", "WTI"]
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ""
            err = e
        except Exception as e:  # network hiccup
            err = e
        time.sleep(5 * (i + 1))
    print("fetch failed:", url, err)
    return 0, ""


def text_of(page):
    return html.unescape(re.sub(r"<[^>]+>", "", page))


def num(s):
    return 0 if s == "." else int(s.replace(",", ""))


def parse_fin(t):
    out = {}
    for k, c in FIN.items():
        i = t.find("CFTC Code #" + c)
        if i < 0:
            continue
        seg = t[i:i + 700]
        m = re.search(r"Open Interest is\s+([\d,]+)", seg)
        line = next((l for l in seg.split("\n") if re.fullmatch(r"\s*[\d,.]+(\s+[\d,.]+){13}\s*", l)), None)
        if m and line:
            n = [num(x) for x in line.split()]
            out[k] = [num(m.group(1)), n[6], n[7], n[3], n[4], n[12], n[13]]
    return out


def parse_dis(t, mp):
    out = {}
    for k, c in mp.items():
        i = t.find("Code-" + c)
        if i < 0:
            continue
        line = next((l for l in t[i:i + 2500].split("\n") if re.match(r"All\s*:", l)), None)
        if not line:
            continue
        p = line.split(":")
        a, b = [num(x) for x in p[2].split()], [num(x) for x in p[3].split()]
        if len(a) == 11 and len(b) == 2:
            out[k] = [num(p[1].strip()), a[5], a[6], a[0] + a[2], a[1] + a[3], b[0], b[1]]
    return out


def report_date(t, kind):
    m = re.search(r"Positions as of (\w+) (\d{1,2}), (\d{4})" if kind == "financial" else r"Futures Only, (\w+) (\d{1,2}), (\d{4})", t)
    return dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))) if m and m.group(1) in MONTHS else None


def fetch_week(tuesday):
    """Return (date, {market: row}) for the report nearest `tuesday`, or None."""
    got = {}
    for kind in ("financial", "other", "petroleum"):
        res = None
        for off in (0, -1, 1, -2, 2):
            d = tuesday + dt.timedelta(days=off)
            url = f"https://www.cftc.gov/sites/default/files/files/dea/cotarchives/{d.year}/futures/{kind}_lf{d:%m%d%y}.htm"
            st, page = get(url)
            if st == 200 and page:
                t = text_of(page)
                rows = parse_fin(t) if kind == "financial" else parse_dis(t, DIS[kind])
                if rows:
                    res = (d, rows)
                    break
        if res is None:  # the newest week may only be on the "current report" page
            st, page = get(f"https://www.cftc.gov/dea/futures/{kind}_lf.htm")
            if st == 200 and page:
                t = text_of(page)
                d = report_date(t, kind)
                if d and abs((d - tuesday).days) <= 2:
                    rows = parse_fin(t) if kind == "financial" else parse_dis(t, DIS[kind])
                    if rows:
                        res = (d, rows)
        if res is None:
            return None
        got[kind] = res
    dates = {v[0] for v in got.values()}
    if len(dates) != 1:
        print("report dates disagree:", dates)
        return None
    rows = {}
    for v in got.values():
        rows.update(v[1])
    if set(rows) != set(ORDER):
        print("missing markets:", set(ORDER) - set(rows))
        return None
    return dates.pop(), rows


def cot_decode(j):
    d = dt.date.fromisoformat(j["d0"])
    dates = [d]
    for x in j["dd"].split(","):
        d += dt.timedelta(days=int(x))
        dates.append(d)
    cols = {}
    for k, s in j["enc"].items():
        cc = []
        for col in s.split("|"):
            v, arr = 0, []
            for x in col.split(","):
                v += int(x)
                arr.append(v)
            cc.append(arr)
        cols[k] = cc
    return dates, cols


def cot_encode(j, dates, cols):
    j["d0"] = dates[0].isoformat()
    j["dd"] = ",".join(str((dates[i] - dates[i - 1]).days) for i in range(1, len(dates)))
    j["enc"] = {k: "|".join(",".join(str(c[0] if i == 0 else c[i] - c[i - 1]) for i in range(len(c))) for c in cc) for k, cc in cols.items()}
    j["checksum"] = sum(v for cc in cols.values() for c in cc for v in c)
    j["built"] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def update_cot(today):
    j = json.load(open(COT_F))
    dates, cols = cot_decode(j)
    added = 0
    nxt = dates[-1] + dt.timedelta(days=7)
    while nxt + dt.timedelta(days=3) <= today:  # report for Tuesday `nxt` is published on Friday
        r = fetch_week(nxt)
        if not r:
            print("COT: report for", nxt, "not available yet")
            break
        d, rows = r
        if d <= dates[-1]:
            break
        dates.append(d)
        for k in ORDER:
            for f in range(7):
                cols[k][f].append(rows[k][f])
        added += 1
        print("COT: added", d)
        nxt = d + dt.timedelta(days=7)
    # self-check: re-download the newest stored week and compare it with the stored numbers
    chk = fetch_week(dates[-1])
    if chk is None:
        print("COT self-check: could not download", dates[-1], "(network or format problem)")
        parse_ok = False
    else:
        bad = [k for k in ORDER if [cols[k][f][-1] for f in range(7)] != chk[1][k]]
        parse_ok = chk[0] == dates[-1] and not bad
        print("COT self-check:", "OK" if parse_ok else f"MISMATCH {chk[0]} {bad}")
    if added:
        cot_encode(j, dates, cols)
        json.dump(j, open(COT_F, "w"), separators=(",", ":"))
    # stale when the newest Tuesday that should be public (published Friday) is more than one week behind
    # the most recent Tuesday whose report (normally Friday, Monday in holiday weeks) has had until Tuesday to be picked up
    expected = today - dt.timedelta(days=(today.weekday() - 1) % 7)
    if today < expected + dt.timedelta(days=7):  # allow holiday weeks, when CFTC publishes on Monday
        expected -= dt.timedelta(days=7)
    stale = dates[-1] < expected
    return added, dates[-1], stale or not parse_ok


def update_macro():
    old = json.load(open(MAC_F))
    new = {}
    for sid in ("WALCL", "WTREGEN", "RRPONTSYD", "DGS2", "DGS10", "DFEDTARU", "IRSTCI01JPM156N"):
        st, txt = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2020-09-01")
        rows = []
        for line in txt.strip().splitlines()[1:]:
            p = line.split(",")
            if len(p) == 2 and p[1] not in (".", ""):
                try:
                    rows.append([p[0], float(p[1]) if "." in p[1] else int(p[1])])
                except ValueError:
                    pass
        prev = old["series"].get(sid, [])
        if not rows or len(rows) < len(prev) - 5 or (prev and rows[-1][0] < prev[-1][0]):
            print("FRED:", sid, "failed sanity check; keeping previous data")
            return False
        new[sid] = rows
    if new != old["series"]:
        old["series"] = new
        old["built"] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        json.dump(old, open(MAC_F, "w"), separators=(",", ":"))
        print("FRED: updated, last", {k: v[-1][0] for k, v in new.items()})
    else:
        print("FRED: no change")
    return True


def main():
    today = dt.datetime.utcnow().date()
    added, last, stale = update_cot(today)
    ok = update_macro()
    try:
        import rates
        rates_ok = rates.main()
    except Exception as e:
        print("RATES: failed", e)
        rates_ok = False
    print("RATES ok =", rates_ok)
    print(f"COT: {added} week(s) added, newest {last}, stale={stale}; FRED ok={ok}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"stale={'true' if (stale or not ok) else 'false'}\n")


if __name__ == "__main__":
    main()
