"""
fetch_data.py - Download all raw series for the SES x Codera FX hackathon.

Sources (all free, no API key):
  * SARB Web API  : EXCX135D (USDZAR, the official series), MMRD403A (JIBAR 3M),
                    GDPL201D (London gold price, USD)
  * FRED          : DTB3 (US 3M T-bill), VIXCLS (VIX), DTWEXBGS (broad USD index),
                    DCOILBRENTEU (Brent)
  * Yahoo Finance : PL=F (platinum futures)

The USDZAR series EXCX135 is published by SARB and distributed via EconData. The
SARB Web API serves the identical series under code EXCX135D. We pull EXCX135 from
EconData as well and check the two against each other in verify_provenance.py.

Files are written to data/raw/snapshots/<today>/<name>.csv with columns
date,value. The revised FRED series also get their full revision history from
ALFRED, in vintages/<FRED code>.csv with columns obs_date,value,realtime_start:
one row for each value an observation has had, dated from the day ALFRED first
shows it. The committed files in data/raw/ are never overwritten: the results
in this repository come from them, and a later download will differ (revisions,
extra days). To adopt a snapshot, copy it over data/raw/ by hand and rerun.
"""
import io
import re
import time
import zipfile
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

TODAY = dt.date.today().isoformat()
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "snapshots" / TODAY
UA = {"User-Agent": "Mozilla/5.0 (hackathon research script)"}


def fetch_sarb(code: str, start: str, end: str = TODAY) -> pd.DataFrame:
    """Pull a SARB time series in 5-year chunks (the server caps rows per request)."""
    frames = []
    s = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    while s <= stop:
        e = min(dt.date(s.year + 5, s.month, s.day), stop)
        url = (f"https://custom.resbank.co.za/SarbWebApi/WebIndicators/Shared/"
               f"GetTimeseriesObservations/{code}/{s}/{e}")
        r = requests.get(url, timeout=30, headers=UA)
        r.raise_for_status()
        obs = r.json()
        if obs:
            frames.append(pd.DataFrame(
                {"date": [o["Period"][:10] for o in obs],
                 "value": [o["Value"] for o in obs]}))
        s = e + dt.timedelta(days=1)
        time.sleep(0.3)
    df = (pd.concat(frames)
            .drop_duplicates("date")
            .assign(date=lambda d: pd.to_datetime(d["date"]))
            .sort_values("date")
            .reset_index(drop=True))
    return df


def fetch_fred(series: str, start: str) -> pd.DataFrame:
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
           f"&cosd={start}&coed={TODAY}")
    df = pd.read_csv(url, na_values=".")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna().reset_index(drop=True)


def fetch_yahoo(symbol: str, start: str) -> pd.DataFrame:
    p1 = int(dt.datetime.fromisoformat(start).timestamp())
    p2 = int(time.time())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?period1={p1}&period2={p2}&interval=1d")
    r = requests.get(url, timeout=30, headers=UA)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]
    close = res["indicators"]["quote"][0]["close"]
    df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").normalize(),
                       "value": close}).dropna()
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def fetch_alfred(series: str) -> pd.DataFrame:
    """Every value each observation of a FRED series has had, from ALFRED's
    download form ("Observations by Real-Time Period"). No API key is needed.
    The form accepts at most 450 vintages a request, so vintages go in chunks;
    each chunk repeats the periods it shares with its neighbours, which the
    de-duplication removes."""
    url = f"https://alfred.stlouisfed.org/series/downloaddata?seid={series}"
    s = requests.Session()
    page = s.get(url, timeout=60, headers=UA).text
    box = page[page.find('id="form_selected_vintage_dates"'):]
    vintages = re.findall(r'value="(\d{4}-\d\d-\d\d)"', box[:box.find("</select>")])
    first, last = (re.search(rf'id="form_obs_{k}_date"[^>]*value="([\d-]+)"', page).group(1)
                   for k in ("start", "end"))
    frames = []
    for i in range(0, len(vintages), 440):
        form = [("form[units]", "lin"), ("form[obs_start_date]", first),
                ("form[obs_end_date]", last)]
        form += [("form[selected_vintage_dates][]", v) for v in vintages[i:i + 441]]
        form += [("form[entered_vintage_dates]", ""), ("form[file_type]", "1"),
                 ("form[file_format]", "csv"), ("form[download_data]", "")]
        for attempt in range(3):        # the form returns the odd 500 under load
            r = s.post(url, data=form, timeout=600, headers={**UA, "Referer": url})
            if r.status_code != 500:
                break
            time.sleep(30)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        csv = next(n for n in z.namelist() if n.endswith(".csv"))
        frames.append(pd.read_csv(io.BytesIO(z.read(csv)), na_values="."))
        time.sleep(2)
    df = (pd.concat(frames)
            .rename(columns={"period_start_date": "obs_date", series: "value",
                             "realtime_start_date": "realtime_start"})
            [["obs_date", "value", "realtime_start"]]
            .dropna()
            .drop_duplicates()
            .sort_values(["obs_date", "realtime_start"]))
    # keep a row only where the value changed from the previous period
    same = (df["obs_date"].eq(df["obs_date"].shift())
            & df["value"].eq(df["value"].shift()))
    return df[~same].reset_index(drop=True)


def main() -> None:
    jobs = [
        ("usdzar",   lambda: fetch_sarb("EXCX135D", "1990-01-01")),
        ("jibar3m",  lambda: fetch_sarb("MMRD403A", "1999-01-01")),
        ("gold",     lambda: fetch_sarb("GDPL201D", "1999-01-01")),
        ("ustbill3m", lambda: fetch_fred("DTB3", "1990-01-01")),
        ("vix",      lambda: fetch_fred("VIXCLS", "1990-01-01")),
        ("usd_broad", lambda: fetch_fred("DTWEXBGS", "2006-01-01")),
        ("brent",    lambda: fetch_fred("DCOILBRENTEU", "1990-01-01")),
        ("platinum", lambda: fetch_yahoo("PL=F", "1999-01-04")),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in jobs:
        df = fn()
        out = OUT / f"{name}.csv"
        df.to_csv(out, index=False)
        print(f"{name:10s} {len(df):6d} obs  {df.date.min().date()} -> {df.date.max().date()}")

    (OUT / "vintages").mkdir(exist_ok=True)
    for series in ["DTB3", "VIXCLS", "DTWEXBGS", "DCOILBRENTEU"]:
        df = fetch_alfred(series)
        df.to_csv(OUT / "vintages" / f"{series}.csv", index=False)
        print(f"{series:12s} {len(df):6d} real-time rows, "
              f"{df.realtime_start.nunique()} vintage dates")


if __name__ == "__main__":
    main()
