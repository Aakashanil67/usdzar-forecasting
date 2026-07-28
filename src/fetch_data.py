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

Every file is written to data/raw/<name>.csv with columns: date,value
"""
import json
import time
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

TODAY = dt.date.today().isoformat()
UA = {"User-Agent": "Mozilla/5.0 (hackathon research script)"}


def fetch_sarb(code: str, start: str, end: str = TODAY) -> pd.DataFrame:
    """Pull a SARB time series in 5-year chunks (robust to server row limits)."""
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
    for name, fn in jobs:
        df = fn()
        out = RAW / f"{name}.csv"
        df.to_csv(out, index=False)
        print(f"{name:10s} {len(df):6d} obs  {df.date.min().date()} -> {df.date.max().date()}")


if __name__ == "__main__":
    main()
