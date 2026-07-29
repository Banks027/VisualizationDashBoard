from pathlib import Path
import datetime
from datetime import date
import numpy as np
import pandas as pd
import csv
import re

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
SOURCE_DIR = Path(r"C:/Users/Viv/Documents/Career readiness/internships/IDX exchange/csv")
START_YEAR, START_MONTH = 2024, 1
PROPERTY_FILTER = "Residential"
PERCENTILES = [10,25,50,75,90]
COLUMN_INDEX = {
    "CRMLSListing": 10,
    "CRMLSSold": 17
}

# Folder containing all monthly CSV files
DATA_FOLDER = Path(r"C:\Users\Viv\Documents\Career readiness\internships\IDX exchange\csv")

# Last completed calendar month
today = date.today()
last_month = today.month - 1
year = today.year
TERMINAL_FLOAT_FORMAT = lambda value: f"{value:,.6f}"

mortgage = pd.read_csv(URL, parse_dates=['observation_date'])
mortgage.columns = ['date', 'rate_30yr_fixed']

def most_recent_completed_month():
    today = date.today()
    y, m = today.year, today.month-1
    return (y-1,12) if m==0 else (y,m)

def monthly_files(prefix):
    ey, em = most_recent_completed_month()
    return [f for p in pd.period_range(f"{START_YEAR}-{START_MONTH:02d}",f"{ey}-{em:02d}",freq="M")
            if (f:=SOURCE_DIR/f"{prefix}{p.year:04d}{p.month:02d}.csv").exists()]

def process(prefix,date_col):

    files=monthly_files(prefix)
    if not files:
        print(f"No files for {prefix}")
        return None
    frames=[pd.read_csv(f,low_memory=False) for f in files]

    print("Rows before concatenation:",sum(len(x) for x in frames))

    df=pd.concat(frames,ignore_index=True)

    print("Rows after concatenation:",len(df))

    print("Unique PropertyTypes:",sorted(df.PropertyType.dropna().astype(str).str.strip().unique()))

    print("Rows before Residential filter:",len(df))


    df=df.query("PropertyType == @PROPERTY_FILTER").copy()

    print("Rows after Residential filter:",len(df))

    nulls=pd.DataFrame({"null_count":df.isna().sum()})

    nulls["null_percent"]=nulls.null_count/len(df)*100


    print(nulls)

    print("Columns >90% null:")

    print(nulls[nulls.null_percent>90])


    stats = (
    df[["ClosePrice", "LivingArea", "DaysOnMarket"]]
    .apply(pd.to_numeric, errors="coerce")
    .describe(percentiles=[p / 100 for p in PERCENTILES])
)
    print(stats)
    
    df.to_csv(SOURCE_DIR/f"{prefix}_filtered_residential.csv",index=False)

    nulls.to_csv(SOURCE_DIR/f"{prefix}_null_summary.csv")

    stats.to_csv(SOURCE_DIR/f"{prefix}_numeric_summary.csv")

    rates=pd.read_csv(URL,parse_dates=["observation_date"])

    rates.columns=["date","rate_30yr_fixed"]

    rates["year_month"]=rates.date.dt.to_period("M")

    rates=rates.groupby("year_month",as_index=False).rate_30yr_fixed.mean()

    df["year_month"]=pd.to_datetime(df[date_col],errors="coerce").dt.to_period("M")
    # Remove rows with dates beyond the latest mortgage month
    latest_rate = rates["year_month"].max()

    before = len(df)

    df = df[df["year_month"] <= latest_rate].copy()

    print(f"Removed {before - len(df)} rows beyond available mortgage data.")
    merged=df.merge(rates,on="year_month",how="left")

    if merged["rate_30yr_fixed"].isna().any():
        missing = merged[merged["rate_30yr_fixed"].isna()]
        print(missing[[date_col, "year_month"]].head())
        raise ValueError("Mortgage-rate merge produced null values.")

    merged.to_csv(
    SOURCE_DIR / f"{prefix}_with_rates.csv",
    index=False
    )

    return merged

if __name__ == "__main__":

    sold = process("CRMLSSold", "CloseDate")
    listing = process("CRMLSListing", "ListingContractDate")

    combined = pd.concat([sold, listing], ignore_index=True, sort=False)

    combined.to_csv(
        SOURCE_DIR / "CRMLS_combined_with_rates.csv",
        index=False
    )
