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



# ===========================
    # WEEK 4-5 REPORTING
    # ===========================

def print_transformation_log():
    print("\n===== Transformation Log =====")

    steps = [
        ("Concatenate monthly files",
         "Creates one dataset for each MLS feed."),
        ("Filter Residential records",
         "Removes non-residential property types."),
        ("Null summary",
         "Measures missing values by column."),
        ("Numeric summary",
         "Summarizes important numeric fields."),
        ("Convert dates",
         "Creates year_month merge key."),
        ("Merge mortgage rates",
         "Adds monthly average 30-year mortgage rate from FRED."),
        ("Remove future dates",
         "Ensures every record has a matching mortgage rate."),
    ]

    for i, (step, reason) in enumerate(steps, start=1):
        print(f"{i}. {step}: {reason}")


def print_row_count_summary(before_rows, after_rows):

    print("\n===== Row Count Summary =====")
    print(f"Rows before processing : {before_rows:,}")
    print(f"Rows after processing  : {after_rows:,}")
    print(f"Rows removed           : {before_rows-after_rows:,}")




def save_dtype_summary(df, output_dir):

    dtypes = pd.DataFrame({
        "Column": df.columns,
        "DataType": df.dtypes.astype(str)
    })

    print("\n===== Data Types =====")
    print(dtypes)

    dtypes.to_csv(
        output_dir / "data_type_summary.csv",
        index=False
    )



def date_consistency_summary(df):

    print("\n===== Date Consistency =====")

    date_columns = [
        c for c in df.columns
        if "Date" in c
    ]

    summary = []

    for col in date_columns:

        converted = pd.to_datetime(
            df[col],
            errors="coerce"
        )

        invalid = converted.isna().sum()

        summary.append({
            "Column": col,
            "Invalid Dates": invalid
        })

    summary = pd.DataFrame(summary)

    print(summary)

    summary.to_csv(
        SOURCE_DIR / "date_consistency_summary.csv",
        index=False
    )



def geographic_summary(df):

    print("\n===== Geographic Quality =====")

    if (
        "Latitude" not in df.columns or
        "Longitude" not in df.columns
    ):
        print("Latitude/Longitude columns not found.")
        return

    invalid = df[
        (~df["Latitude"].between(-90,90)) |
        (~df["Longitude"].between(-180,180))
    ]

    print(f"Invalid coordinate records: {len(invalid)}")

    invalid.to_csv(
        SOURCE_DIR / "invalid_coordinates.csv",
        index=False
    )





    print_transformation_log()

    # Row count summary
    before_rows = 0

    for prefix in ["CRMLSSold", "CRMLSListing"]:
        files = monthly_files(prefix)
        for f in files:
            before_rows += len(pd.read_csv(f, low_memory=False))

    after_rows = len(combined)

    print_row_count_summary(before_rows, after_rows)

    # Save data types
    save_dtype_summary(combined, SOURCE_DIR)

    # Date consistency
    date_consistency_summary(combined)

    # Geographic quality
    geographic_summary(combined)

    # Numeric validation
    validate_numeric_fields(combined, SOURCE_DIR, "combined")

    print("\nWeek 4-5 reporting complete.")


def validate_numeric_fields(df, output_dir, prefix):

    checks = []

    # ClosePrice
    if "ClosePrice" in df.columns:
        price = pd.to_numeric(df["ClosePrice"], errors="coerce")

        checks.append({
            "Field": "ClosePrice",
            "Negative Values": (price < 0).sum(),
            "Zero Values": (price == 0).sum(),
            "Null Values": price.isna().sum()
        })

    # LivingArea
    if "LivingArea" in df.columns:
        area = pd.to_numeric(df["LivingArea"], errors="coerce")

        checks.append({
            "Field": "LivingArea",
            "Negative Values": (area < 0).sum(),
            "Zero Values": (area == 0).sum(),
            "Null Values": area.isna().sum()
        })

    # DaysOnMarket
    if "DaysOnMarket" in df.columns:
        dom = pd.to_numeric(df["DaysOnMarket"], errors="coerce")

        checks.append({
            "Field": "DaysOnMarket",
            "Negative Values": (dom < 0).sum(),
            "Zero Values": (dom == 0).sum(),
            "Null Values": dom.isna().sum()
        })

    validation = pd.DataFrame(checks)

    print("\n===== Numeric Validation =====")
    print(validation)

    validation.to_csv(
        output_dir / f"{prefix}_numeric_validation.csv",
        index=False
    )

    return validation
