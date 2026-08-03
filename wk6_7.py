from __future__ import annotations

from pathlib import Path
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = SCRIPT_DIR.parents[1] / "csv"
if not CSV_DIR.exists():
    CSV_DIR = Path(r"C:\Users\Viv\Documents\Career readiness\internships\IDX exchange\csv")

START_YEAR, START_MONTH = 2024, 1
PERCENTILES = [10, 25, 50, 75, 90]
SCHOOL_DISTRICT_URL = (
    "https://data.ca.gov/dataset/california-school-district-areas-2024-25/"
    "resource/7dfaf005-58eb-45db-93b1-7aff091b2172"
)


def most_recent_completed_month() -> tuple[int, int]:
    today = date.today()
    year, month = today.year, today.month - 1
    return (year - 1, 12) if month == 0 else (year, month)


def monthly_files(prefix: str) -> list[Path]:
    end_year, end_month = most_recent_completed_month()
    files = []
    for period in pd.period_range(
        f"{START_YEAR}-{START_MONTH:02d}",
        f"{end_year}-{end_month:02d}",
        freq="M",
    ):
        file_path = CSV_DIR / f"{prefix}{period.year:04d}{period.month:02d}.csv"
        if file_path.exists():
            files.append(file_path)
    return files


def read_monthly_feed(prefix: str) -> pd.DataFrame:
    files = monthly_files(prefix)
    if not files:
        raise FileNotFoundError(f"No monthly files found for {prefix}")

    frames = [pd.read_csv(file_path, low_memory=False) for file_path in files]
    print(f"{prefix}: rows before concatenation = {sum(len(frame) for frame in frames):,}")
    combined = pd.concat(frames, ignore_index=True)
    print(f"{prefix}: rows after concatenation  = {len(combined):,}")
    return combined


def coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def coerce_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


def engineer_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = coerce_numeric(
        df,
        ["ClosePrice", "OriginalListPrice", "LivingArea", "DaysOnMarket", "Latitude", "Longitude"],
    )
    df = coerce_dates(df, ["CloseDate", "ListingContractDate", "PurchaseContractDate"])

    if {"ClosePrice", "OriginalListPrice"}.issubset(df.columns):
        ratio = np.where(
            df["OriginalListPrice"] > 0,
            df["ClosePrice"] / df["OriginalListPrice"],
            np.nan,
        )
        df["PriceRatio"] = ratio
        df["CloseToOriginalListRatio"] = ratio

    if {"ClosePrice", "LivingArea"}.issubset(df.columns):
        ppsf = np.where(
            df["LivingArea"] > 0,
            df["ClosePrice"] / df["LivingArea"],
            np.nan,
        )
        df["PricePerSqFt"] = ppsf
        df["PPSF"] = ppsf

    if "CloseDate" in df.columns:
        df["Year"] = df["CloseDate"].dt.year
        df["Month"] = df["CloseDate"].dt.month
        df["YrMo"] = df["CloseDate"].dt.strftime("%Y-%m")

    if {"PurchaseContractDate", "ListingContractDate"}.issubset(df.columns):
        df["ListingToContractDays"] = (df["PurchaseContractDate"] - df["ListingContractDate"]).dt.days
        df.loc[df["ListingToContractDays"] < 0, "ListingToContractDays"] = np.nan

    if {"CloseDate", "PurchaseContractDate"}.issubset(df.columns):
        df["ContractToCloseDays"] = (df["CloseDate"] - df["PurchaseContractDate"]).dt.days
        df.loc[df["ContractToCloseDays"] < 0, "ContractToCloseDays"] = np.nan

    if "DaysOnMarket" in df.columns:
        df["DaysOnMarket"] = pd.to_numeric(df["DaysOnMarket"], errors="coerce")

    return df


def summarize_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    present = [column for column in columns if column in df.columns]
    if not present:
        return pd.DataFrame()
    return df[present].describe(percentiles=[percentile / 100 for percentile in PERCENTILES]).round(2)


def build_summary_table(df: pd.DataFrame, group_cols: list[str], output_name: str) -> pd.DataFrame:
    available_cols = [column for column in group_cols if column in df.columns]
    if len(available_cols) != len(group_cols):
        missing = [column for column in group_cols if column not in df.columns]
        print(f"Skipping {output_name}; missing columns: {missing}")
        return pd.DataFrame()

    metrics = {
        "Records": ("ClosePrice", "size"),
        "MedianClosePrice": ("ClosePrice", "median"),
        "MedianPPSF": ("PricePerSqFt", "median"),
        "MedianDOM": ("DaysOnMarket", "median"),
        "MedianPriceRatio": ("PriceRatio", "median"),
    }

    summary = df.groupby(available_cols, dropna=False).agg(**metrics).reset_index().round(2)
    summary.to_csv(CSV_DIR / output_name, index=False)
    print(f"Saved {output_name}")
    print(summary.head(10))
    return summary


def segment_analysis(df: pd.DataFrame) -> None:
    build_summary_table(df, ["PropertyType", "PropertySubType"], "week6_propertytype_subtype_summary.csv")
    build_summary_table(df, ["CountyOrParish", "MLSAreaMajor"], "week6_county_mlsarea_summary.csv")
    build_summary_table(df, ["ListOfficeName", "BuyerOfficeName"], "week6_office_competition_summary.csv")


def add_school_districts(df: pd.DataFrame, district_source: str = SCHOOL_DISTRICT_URL) -> pd.DataFrame:
    if {"Latitude", "Longitude"}.difference(df.columns):
        print("Skipping school district join; Latitude/Longitude not available.")
        return df

    working = df.copy()
    working["Latitude"] = pd.to_numeric(working["Latitude"], errors="coerce")
    working["Longitude"] = pd.to_numeric(working["Longitude"], errors="coerce")

    valid_mask = working["Latitude"].between(-90, 90) & working["Longitude"].between(-180, 180)
    if not valid_mask.any():
        print("Skipping school district join; no valid coordinates found.")
        return working

    try:
        districts = gpd.read_file(district_source)
    except Exception as exc:
        print(f"School district join unavailable: {exc}")
        return working

    if getattr(districts, "crs", None) is not None:
        districts = districts.to_crs("EPSG:4326")

    district_name_candidates = [
        column
        for column in districts.columns
        if "DISTRICT" in column.upper() and not column.upper().startswith("SHAPE_")
    ]
    district_name_column = district_name_candidates[0] if district_name_candidates else None

    points = gpd.GeoDataFrame(
        working.loc[valid_mask].copy(),
        geometry=gpd.points_from_xy(
            working.loc[valid_mask, "Longitude"],
            working.loc[valid_mask, "Latitude"],
        ),
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(points, districts, how="left", predicate="within")
    if district_name_column and district_name_column in joined.columns:
        joined["SchoolDistrict"] = joined[district_name_column]
    else:
        joined["SchoolDistrict"] = np.nan

    working.loc[valid_mask, "SchoolDistrict"] = joined["SchoolDistrict"].values
    return working


def add_iqr_flags(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    bounds_rows = []

    for column in columns:
        if column not in working.columns:
            continue

        values = pd.to_numeric(working[column], errors="coerce")
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        flag_column = f"{column}_IQRFlag"
        invalid_column = f"{column}_Invalid"
        working[invalid_column] = values.le(0) if column == "ClosePrice" else values.isna()
        working[flag_column] = values.notna() & ((values < lower) | (values > upper))

        bounds_rows.append(
            {
                "Field": column,
                "Q1": q1,
                "Q3": q3,
                "IQR": iqr,
                "LowerBound": lower,
                "UpperBound": upper,
                "InvalidCount": int(working[invalid_column].sum()),
                "OutlierCount": int(working[flag_column].sum()),
            }
        )

    flag_columns = [column for column in working.columns if column.endswith("_IQRFlag")]
    if flag_columns:
        working["AnyIQRFlag"] = working[flag_columns].any(axis=1)
    else:
        working["AnyIQRFlag"] = False

    bounds = pd.DataFrame(bounds_rows).round(2)
    return working, bounds


def week7_filtered_outputs(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    analysis = df.copy()
    if "ClosePrice" in analysis.columns:
        analysis = analysis[analysis["ClosePrice"].notna() & (analysis["ClosePrice"] > 0)].copy()

    flagged, bounds = add_iqr_flags(analysis, ["ClosePrice", "LivingArea", "DaysOnMarket"])
    clean = flagged[~flagged["AnyIQRFlag"]].copy()

    comparison = pd.DataFrame(
        {
            "Metric": ["Records", "MedianClosePrice", "MedianLivingArea", "MedianDaysOnMarket", "MedianPriceRatio", "MedianPPSF"],
            "BeforeFiltering": [
                len(flagged),
                flagged["ClosePrice"].median() if "ClosePrice" in flagged.columns else np.nan,
                flagged["LivingArea"].median() if "LivingArea" in flagged.columns else np.nan,
                flagged["DaysOnMarket"].median() if "DaysOnMarket" in flagged.columns else np.nan,
                flagged["CloseToOriginalListRatio"].median() if "CloseToOriginalListRatio" in flagged.columns else np.nan,
                flagged["PricePerSqFt"].median() if "PricePerSqFt" in flagged.columns else np.nan,
            ],
            "AfterFiltering": [
                len(clean),
                clean["ClosePrice"].median() if "ClosePrice" in clean.columns else np.nan,
                clean["LivingArea"].median() if "LivingArea" in clean.columns else np.nan,
                clean["DaysOnMarket"].median() if "DaysOnMarket" in clean.columns else np.nan,
                clean["CloseToOriginalListRatio"].median() if "CloseToOriginalListRatio" in clean.columns else np.nan,
                clean["PricePerSqFt"].median() if "PricePerSqFt" in clean.columns else np.nan,
            ],
        }
    )

    flagged.to_csv(CSV_DIR / "week7_full_flagged_dataset.csv", index=False)
    clean.to_csv(CSV_DIR / "week7_clean_filtered_dataset.csv", index=False)
    bounds.to_csv(CSV_DIR / "week7_iqr_bounds.csv", index=False)
    comparison.to_csv(CSV_DIR / "week7_filter_comparison.csv", index=False)

    print("\nWeek 7 IQR bounds")
    print(bounds)
    print("\nWeek 7 filter comparison")
    print(comparison)
    return flagged, clean, comparison


def save_sample_output(df: pd.DataFrame, prefix: str) -> None:
    preferred_columns = [
        "PropertyType",
        "PropertySubType",
        "CountyOrParish",
        "MLSAreaMajor",
        "ClosePrice",
        "OriginalListPrice",
        "LivingArea",
        "DaysOnMarket",
        "CloseDate",
        "PriceRatio",
        "CloseToOriginalListRatio",
        "PricePerSqFt",
        "YrMo",
        "ListingToContractDays",
        "ContractToCloseDays",
        "SchoolDistrict",
    ]
    columns = [column for column in preferred_columns if column in df.columns]
    sample = df[columns].head(20).copy()
    sample.to_csv(CSV_DIR / f"{prefix}_engineered_metric_sample.csv", index=False)
    print(f"\n{prefix} engineered sample")
    print(sample)


def run_feed(prefix: str, date_column: str) -> pd.DataFrame:
    df = read_monthly_feed(prefix)
    df["SourceFeed"] = prefix
    df["YearMonth"] = pd.to_datetime(df[date_column], errors="coerce").dt.to_period("M")
    df = engineer_metrics(df)
    return df


def main(include_school_districts: bool = True) -> None:
    sold = run_feed("CRMLSSold", "CloseDate")
    listing = run_feed("CRMLSListing", "ListingContractDate")

    combined = pd.concat([sold, listing], ignore_index=True, sort=False)
    combined = engineer_metrics(combined)

    if include_school_districts:
        combined = add_school_districts(combined)

    combined.to_csv(CSV_DIR / "CRMLS_combined_engineered.csv", index=False)

    print("\nWeek 6 numeric summary (sold feed)")
    print(summarize_numeric(sold, ["ClosePrice", "OriginalListPrice", "LivingArea", "DaysOnMarket", "PricePerSqFt", "PriceRatio"]))

    save_sample_output(sold, "CRMLSSold")
    save_sample_output(listing, "CRMLSListing")

    segment_analysis(combined)

    flagged, clean, comparison = week7_filtered_outputs(combined)

    print("\nSaved datasets")
    print(f"Full flagged rows: {len(flagged):,}")
    print(f"Clean filtered rows: {len(clean):,}")
    print(comparison)


if __name__ == "__main__":
    main()