"""
================================================================================
DASHBOARD DATA GENERATOR  (runs in GitHub Actions - NO CORS problem)
Writes dashboard_data.json consumed by index.html
--------------------------------------------------------------------------------
Funds  (mfapi.in): Today NAV+date, ATH NAV, % from ATH, at-ATH flag,
                   1Y return, 2Y return (total), 2Y CAGR (annualised).
Indices(yfinance): Current level+date, 1Y return, 2Y return, 2Y CAGR
                   for Sensex, Nifty 50, Nifty Midcap 100, Nifty Smallcap 100.
================================================================================
"""
import json, time, sys
import datetime as dt
import requests

# ---- 23 FUNDS (21 Indian + 2 Foreign) ----
INDIAN_FUNDS = {
    "Axis ELSS Tax Saver Direct Plan-Growth": 120503,
    "Axis Large Cap Fund - Direct Plan - Growth": 120465,
    "Axis Midcap Fund Direct Plan - Growth": 120509,
    "Axis Small Cap Fund - Direct Plan - Growth": 120493,
    "DSP Small Cap Fund - Direct Plan - Growth": 119551,
    "Franklin India Focused Equity Fund Direct Growth": 119220,
    "Franklin India Smaller Companies Fund Direct Growth": 119253,
    "HDFC Flexi Cap Fund - Direct Plan - Growth Option": 118955,
    "HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth": 118951,
    "HDFC Value Fund - Direct Plan - Growth": 118953,
    "ICICI Prudential Business Cycle Fund Direct Growth": 148651,
    "ICICI Prudential Flexicap Fund Direct Growth": 120719,
    "ICICI Prudential Bluechip Fund Direct Plan - Growth": 120718,
    "ICICI Prudential Value Fund Direct Plan - Growth": 120323,
    "Mirae Asset Emerging Bluechip Fund Direct Plan - Growth": 120474,
    "Mirae Asset Large Cap Fund Direct Plan - Growth": 120473,
    "Nippon India Focused Equity Fund Direct Growth": 119241,
    "Nippon India Small Cap Fund Direct Growth": 119244,
    "Parag Parikh Flexi Cap Fund Direct Plan - Growth": 119456,
    "SBI Focused Equity Fund Direct Plan - Growth": 120595,
    "Tata Value Fund Direct Plan - Growth": 143835,
}
FOREIGN_FUNDS = {
    "Mirae Asset NYSE FANG+ ETF FoF Direct Growth": 120749,
    "Motilal Oswal Nasdaq 100 FOF Direct Growth": 120999,
}
ALL_FUNDS = [(n, c, "INDIAN") for n, c in INDIAN_FUNDS.items()] + \
            [(n, c, "FOREIGN") for n, c in FOREIGN_FUNDS.items()]

# ---- 4 INDICES (Yahoo Finance tickers) ----
INDICES = {
    "BSE Sensex":          "^BSESN",
    "Nifty 50":            "^NSEI",
    "Nifty Midcap 100":    "^CRSMID",
    "Nifty Smallcap 100":  "^CNXSC",
}


def get_with_retry(url, attempts=3, timeout=20):
    last = None
    for a in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            if a < attempts:
                time.sleep(1.5 * a)
    raise last


def nearest(series, target, tol_days):
    """series = list of (date, value) ascending. Nearest value to target within tol."""
    best, best_diff = None, None
    for d, v in series:
        diff = abs((d - target).days)
        if best_diff is None or diff < best_diff:
            best_diff, best = diff, v
    if best is None or best_diff > tol_days:
        return None
    return best


# ------------------------------- FUNDS ---------------------------------------
def process_fund(name, code, ftype):
    try:
        r = get_with_retry(f"https://api.mfapi.in/mf/{code}")
        raw = r.json().get("data", [])
        series = []
        for row in raw:
            try:
                d = dt.datetime.strptime(row["date"], "%d-%m-%Y").date()
                series.append((d, float(row["nav"])))
            except Exception:
                pass
        series.sort(key=lambda x: x[0])
        if len(series) < 2:
            return {"name": name, "type": ftype, "error": True}

        today_d, today_nav = series[-1]
        ath = max(n for _, n in series)
        from_ath = (today_nav / ath - 1) * 100
        is_ath = today_nav >= ath * 0.95

        n1 = nearest(series, today_d.replace(year=today_d.year - 1), 30)
        n2 = nearest(series, today_d.replace(year=today_d.year - 2), 45)
        r1y = (today_nav / n1 - 1) * 100 if n1 else None
        r2y = (today_nav / n2 - 1) * 100 if n2 else None
        r2y_cagr = ((today_nav / n2) ** 0.5 - 1) * 100 if n2 else None

        return {
            "name": name, "type": ftype, "error": False,
            "todayNav": round(today_nav, 2), "todayDate": today_d.isoformat(),
            "ath": round(ath, 2), "fromAth": round(from_ath, 2), "isAth": is_ath,
            "r1y": round(r1y, 2) if r1y is not None else None,
            "r2y": round(r2y, 2) if r2y is not None else None,
            "r2yCagr": round(r2y_cagr, 2) if r2y_cagr is not None else None,
        }
    except Exception as e:
        print(f"  ! fund {name}: {e}", file=sys.stderr)
        return {"name": name, "type": ftype, "error": True}


# ------------------------------ INDICES --------------------------------------
def process_index(name, ticker):
    try:
        import yfinance as yf
        # Full history so the all-time high is genuine, not just a 2-year peak
        df = yf.download(ticker, period="max", progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        try:
            close = close.squeeze()
        except Exception:
            pass
        series = [(ts.date(), float(v)) for ts, v in close.items()]
        series.sort(key=lambda x: x[0])
        if len(series) < 2:
            return {"name": name, "error": True}

        today_d, level = series[-1]
        ath = max(v for _, v in series)
        from_ath = (level / ath - 1) * 100
        is_ath = level >= ath * 0.95

        c1 = nearest(series, today_d.replace(year=today_d.year - 1), 20)
        c2 = nearest(series, today_d.replace(year=today_d.year - 2), 25)
        r1y = (level / c1 - 1) * 100 if c1 else None
        r2y = (level / c2 - 1) * 100 if c2 else None
        r2y_cagr = ((level / c2) ** 0.5 - 1) * 100 if c2 else None

        return {
            "name": name, "ticker": ticker, "error": False,
            "level": round(level, 2), "date": today_d.isoformat(),
            "ath": round(ath, 2), "fromAth": round(from_ath, 2), "isAth": is_ath,
            "r1y": round(r1y, 2) if r1y is not None else None,
            "r2y": round(r2y, 2) if r2y is not None else None,
            "r2yCagr": round(r2y_cagr, 2) if r2y_cagr is not None else None,
        }
    except Exception as e:
        print(f"  ! index {name}: {e}", file=sys.stderr)
        return {"name": name, "ticker": ticker, "error": True}


def main():
    print(f"Fetching {len(ALL_FUNDS)} funds...")
    funds = []
    for i, (name, code, ftype) in enumerate(ALL_FUNDS, 1):
        res = process_fund(name, code, ftype)
        print(f"  [{i:2d}] {name[:48]:<48} {'OK' if not res.get('error') else 'FAILED'}")
        funds.append(res)
        time.sleep(0.1)

    print(f"\nFetching {len(INDICES)} indices...")
    indices = []
    for name, ticker in INDICES.items():
        res = process_index(name, ticker)
        lvl = res.get("level")
        print(f"  {name:<20} {ticker:<12} {('OK  '+str(lvl)) if not res.get('error') else 'FAILED'}")
        indices.append(res)

    out = {
        "generatedAt": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "indices": indices,
        "funds": funds,
    }
    with open("dashboard_data.json", "w") as f:
        json.dump(out, f, indent=2)

    okf = sum(1 for x in funds if not x.get("error"))
    oki = sum(1 for x in indices if not x.get("error"))
    print(f"\nDone. Funds {okf}/{len(ALL_FUNDS)}, Indices {oki}/{len(INDICES)}. Wrote dashboard_data.json")


if __name__ == "__main__":
    main()
