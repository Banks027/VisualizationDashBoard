from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = SCRIPT_DIR.parents[1] / "csv"
if not CSV_DIR.exists():
    CSV_DIR = Path(r"C:\Users\Viv\Documents\Career readiness\internships\IDX exchange\csv")

START_YEAR, START_MONTH = 2024, 1
PERCENTILES = [10, 25, 50, 75, 90]
SCHOOL_DISTRICT_GEOJSON_URL = (
    "https://gis.data.ca.gov/api/download/v1/items/48870daecfe14c6ab376f6a673491914/geojson?layers=0"
)
FRED_MORTGAGE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"

CORE_FIELDS = {
    "PropertyType",
    "PropertySubType",
    "CountyOrParish",
    "MLSAreaMajor",
    "CloseDate",
    "ListingContractDate",
    "PurchaseContractDate",
    "ContractStatusChangeDate",
    "ClosePrice",
    "ListPrice",
    "OriginalListPrice",
    "LivingArea",
    "LotSizeAcres",
    "BedroomsTotal",
    "BathroomsTotalInteger",
    "DaysOnMarket",
    "YearBuilt",
    "Latitude",
    "Longitude",
    "ListOfficeName",
    "BuyerOfficeName",
}


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


def filter_residential(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    working = df.copy()
    if "PropertyType" not in working.columns:
        print(f"{prefix}: PropertyType missing; residential filter skipped.")
        return working

    property_type_counts = (
        working["PropertyType"]
        .fillna("<NA>")
        .astype(str)
        .str.strip()
        .value_counts(dropna=False)
        .rename_axis("PropertyType")
        .reset_index(name="Records")
    )
    property_type_counts.to_csv(CSV_DIR / f"{prefix}_property_type_counts.csv", index=False)

    # Week 1 row-count checkpoints before and after Residential-only filtering.
    before_filter = len(working)
    residential_mask = working["PropertyType"].astype(str).str.casefold().eq("residential")
    filtered = working.loc[residential_mask].copy()
    after_filter = len(filtered)
    print(f"{prefix}: rows before Residential filter = {before_filter:,}")
    print(f"{prefix}: rows after Residential filter  = {after_filter:,}")
    return filtered


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
        [
            "ClosePrice",
            "ListPrice",
            "OriginalListPrice",
            "LivingArea",
            "LotSizeAcres",
            "BedroomsTotal",
            "BathroomsTotalInteger",
            "DaysOnMarket",
            "YearBuilt",
            "Latitude",
            "Longitude",
        ],
    )
    df = coerce_dates(df, ["CloseDate", "ListingContractDate", "PurchaseContractDate", "ContractStatusChangeDate"])
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    if "ClosePrice" in df.columns or "ListPrice" in df.columns:
        close_price = df["ClosePrice"] if "ClosePrice" in df.columns else pd.Series(np.nan, index=df.index)
        list_price = df["ListPrice"] if "ListPrice" in df.columns else pd.Series(np.nan, index=df.index)
        df["MarketPrice"] = close_price.where(close_price.notna() & (close_price > 0), list_price)
        df.loc[df["MarketPrice"] <= 0, "MarketPrice"] = np.nan

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

    if "CloseDate" in df.columns and df["CloseDate"].notna().any():
        df["Year"] = df["CloseDate"].dt.year
        df["Month"] = df["CloseDate"].dt.month
        df["YrMo"] = df["CloseDate"].dt.strftime("%Y-%m")
    elif "ListingContractDate" in df.columns:
        df["Year"] = df["ListingContractDate"].dt.year
        df["Month"] = df["ListingContractDate"].dt.month
        df["YrMo"] = df["ListingContractDate"].dt.strftime("%Y-%m")

    if {"PurchaseContractDate", "ListingContractDate"}.issubset(df.columns):
        df["ListingToContractDays"] = (df["PurchaseContractDate"] - df["ListingContractDate"]).dt.days
        df.loc[df["ListingToContractDays"] < 0, "ListingToContractDays"] = np.nan

    if {"CloseDate", "PurchaseContractDate"}.issubset(df.columns):
        df["ContractToCloseDays"] = (df["CloseDate"] - df["PurchaseContractDate"]).dt.days
        df.loc[df["ContractToCloseDays"] < 0, "ContractToCloseDays"] = np.nan

    if "DaysOnMarket" in df.columns:
        df["DaysOnMarket"] = pd.to_numeric(df["DaysOnMarket"], errors="coerce")

    return df


def dataset_structure_reports(df: pd.DataFrame, prefix: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, cols = df.shape
    print(f"{prefix}: rows={rows:,}, columns={cols:,}")

    dtypes_report = (
        pd.DataFrame({"Column": df.columns, "Dtype": [str(dtype) for dtype in df.dtypes]})
        .sort_values("Column")
        .reset_index(drop=True)
    )
    dtypes_report.to_csv(CSV_DIR / f"{prefix}_dtypes_report.csv", index=False)

    null_counts = df.isna().sum()
    missing_report = (
        pd.DataFrame(
            {
                "Column": null_counts.index,
                "MissingCount": null_counts.values,
                "MissingPct": (null_counts.values / len(df) * 100) if len(df) else 0.0,
            }
        )
        .sort_values(["MissingPct", "MissingCount"], ascending=False)
        .reset_index(drop=True)
    )
    missing_report["FlagOver90PctMissing"] = missing_report["MissingPct"] > 90
    missing_report.to_csv(CSV_DIR / f"{prefix}_missing_value_report.csv", index=False)

    high_missing = missing_report.loc[missing_report["FlagOver90PctMissing"]].copy()
    high_missing.to_csv(CSV_DIR / f"{prefix}_high_missing_over_90pct.csv", index=False)
    print(f"{prefix}: columns with >90% missing = {len(high_missing):,}")

    market_fields = [column for column in CORE_FIELDS if column in df.columns]
    metadata_fields = [column for column in df.columns if column not in set(market_fields)]
    pd.DataFrame({"MarketAnalysisFields": market_fields}).to_csv(
        CSV_DIR / f"{prefix}_market_analysis_fields.csv", index=False
    )
    pd.DataFrame({"MetadataFields": metadata_fields}).to_csv(CSV_DIR / f"{prefix}_metadata_fields.csv", index=False)

    return missing_report, high_missing


def numeric_distribution_review(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    fields = [
        "ClosePrice",
        "ListPrice",
        "OriginalListPrice",
        "LivingArea",
        "LotSizeAcres",
        "BedroomsTotal",
        "BathroomsTotalInteger",
        "DaysOnMarket",
        "YearBuilt",
    ]
    present_fields = [field for field in fields if field in df.columns]
    if not present_fields:
        return pd.DataFrame()

    working = coerce_numeric(df.copy(), present_fields)
    rows: list[dict[str, float | int | str]] = []

    for field in present_fields:
        series = working[field].replace([np.inf, -np.inf], np.nan)
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_count = int(((series < lower) | (series > upper)).sum())

        rows.append(
            {
                "Field": field,
                "NonNull": int(series.notna().sum()),
                "Min": series.min(),
                "P10": series.quantile(0.10),
                "P25": q1,
                "Median": series.median(),
                "Mean": series.mean(),
                "P75": q3,
                "P90": series.quantile(0.90),
                "P95": series.quantile(0.95),
                "P99": series.quantile(0.99),
                "Max": series.max(),
                "IQRLower": lower,
                "IQRUpper": upper,
                "IQROutlierCount": outlier_count,
            }
        )

    report = pd.DataFrame(rows).round(2)
    report.to_csv(CSV_DIR / f"{prefix}_numeric_distribution_report.csv", index=False)

    try:
        import matplotlib.pyplot as plt

        for field in present_fields:
            series = working[field].replace([np.inf, -np.inf], np.nan).dropna()
            if series.empty:
                continue

            fig, axes = plt.subplots(1, 2, figsize=(12, 4))
            axes[0].hist(series, bins=50)
            axes[0].set_title(f"{prefix} {field} Histogram")
            axes[0].set_xlabel(field)
            axes[0].set_ylabel("Frequency")
            axes[1].boxplot(series, orientation="horizontal")
            axes[1].set_title(f"{prefix} {field} Boxplot")
            axes[1].set_xlabel(field)
            fig.tight_layout()
            fig.savefig(CSV_DIR / f"{prefix}_{field}_hist_box.png", dpi=150)
            plt.close(fig)
    except Exception as exc:
        print(f"{prefix}: plot generation skipped ({exc})")

    return report


def suggested_question_summary(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    rows = []

    if "PropertyType" in df.columns:
        residential_share = (
            df["PropertyType"].astype(str).str.casefold().eq("residential").mean() * 100 if len(df) else np.nan
        )
        rows.append({"Question": "Residential share (%)", "Value": residential_share})

    if "ClosePrice" in df.columns:
        rows.append({"Question": "Median close price", "Value": pd.to_numeric(df["ClosePrice"], errors="coerce").median()})
        rows.append({"Question": "Average close price", "Value": pd.to_numeric(df["ClosePrice"], errors="coerce").mean()})

    if "DaysOnMarket" in df.columns:
        dom = pd.to_numeric(df["DaysOnMarket"], errors="coerce")
        rows.append({"Question": "Median days on market", "Value": dom.median()})
        rows.append({"Question": "Average days on market", "Value": dom.mean()})

    if {"ClosePrice", "OriginalListPrice"}.issubset(df.columns):
        close_price = pd.to_numeric(df["ClosePrice"], errors="coerce")
        original_list = pd.to_numeric(df["OriginalListPrice"], errors="coerce")
        valid = original_list > 0
        ratio = pd.Series(np.nan, index=df.index)
        ratio.loc[valid] = close_price.loc[valid] / original_list.loc[valid]
        above = (ratio > 1).mean() * 100
        below_or_equal = (ratio <= 1).mean() * 100
        rows.append({"Question": "Pct sold above list", "Value": above})
        rows.append({"Question": "Pct sold at/below list", "Value": below_or_equal})

    if {"ListingContractDate", "CloseDate"}.issubset(df.columns):
        listing_date = pd.to_datetime(df["ListingContractDate"], errors="coerce")
        close_date = pd.to_datetime(df["CloseDate"], errors="coerce")
        rows.append(
            {
                "Question": "Date issue count (ListingContractDate > CloseDate)",
                "Value": int((listing_date > close_date).sum()),
            }
        )

    summary = pd.DataFrame(rows).round(2)
    summary.to_csv(CSV_DIR / f"{prefix}_eda_question_summary.csv", index=False)

    if {"CountyOrParish", "ClosePrice"}.issubset(df.columns):
        county_summary = (
            df.groupby("CountyOrParish", dropna=False)["ClosePrice"]
            .median()
            .sort_values(ascending=False)
            .reset_index(name="MedianClosePrice")
        )
        county_summary.to_csv(CSV_DIR / f"{prefix}_county_median_closeprice.csv", index=False)
    return summary


def fetch_fred_mortgage_monthly() -> pd.DataFrame:
    mortgage = pd.read_csv(FRED_MORTGAGE_URL)
    if "DATE" in mortgage.columns:
        mortgage = mortgage.rename(columns={"DATE": "date", "MORTGAGE30US": "rate_30yr_fixed"})
    elif "observation_date" in mortgage.columns:
        mortgage = mortgage.rename(
            columns={"observation_date": "date", "MORTGAGE30US": "rate_30yr_fixed"}
        )
    else:
        raise ValueError("Unexpected FRED schema: missing DATE/observation_date column")

    mortgage["date"] = pd.to_datetime(mortgage["date"], errors="coerce")
    mortgage["rate_30yr_fixed"] = pd.to_numeric(mortgage["rate_30yr_fixed"], errors="coerce")
    mortgage = mortgage.dropna(subset=["date", "rate_30yr_fixed"]).copy()
    mortgage["year_month"] = mortgage["date"].dt.to_period("M")
    monthly = mortgage.groupby("year_month", as_index=False)["rate_30yr_fixed"].mean()
    monthly.to_csv(CSV_DIR / "fred_mortgage30us_monthly.csv", index=False)
    return monthly


def enrich_with_mortgage_rate(df: pd.DataFrame, prefix: str, date_column: str, mortgage_monthly: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    if date_column not in working.columns:
        print(f"{prefix}: {date_column} missing; mortgage merge skipped.")
        return working

    working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
    working["year_month"] = working[date_column].dt.to_period("M")
    enriched = working.merge(mortgage_monthly, on="year_month", how="left")

    valid_date_rows = enriched["year_month"].notna()
    null_rate_count = int(enriched.loc[valid_date_rows, "rate_30yr_fixed"].isna().sum())
    print(f"{prefix}: null mortgage rates after merge (dated rows only) = {null_rate_count:,}")

    enriched.to_csv(CSV_DIR / f"{prefix}_with_mortgage_rate.csv", index=False)
    pd.DataFrame(
        {
            "Dataset": [prefix],
            "Rows": [len(enriched)],
            "RowsWithValidYearMonth": [int(valid_date_rows.sum())],
            "NullRateRows": [null_rate_count],
        }
    ).to_csv(CSV_DIR / f"{prefix}_mortgage_merge_validation.csv", index=False)
    return enriched


def clean_dataset(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    working = df.copy()
    before_rows = len(working)

    date_columns = ["CloseDate", "PurchaseContractDate", "ListingContractDate", "ContractStatusChangeDate"]
    numeric_columns = [
        "ClosePrice",
        "ListPrice",
        "OriginalListPrice",
        "LivingArea",
        "DaysOnMarket",
        "BedroomsTotal",
        "BathroomsTotalInteger",
        "Latitude",
        "Longitude",
    ]
    working = coerce_dates(working, [column for column in date_columns if column in working.columns])
    working = coerce_numeric(working, [column for column in numeric_columns if column in working.columns])
    working.replace([np.inf, -np.inf], np.nan, inplace=True)

    if "ClosePrice" in working.columns:
        working["ClosePrice_invalid_flag"] = working["ClosePrice"].isna() | (working["ClosePrice"] <= 0)
    if "LivingArea" in working.columns:
        working["LivingArea_invalid_flag"] = working["LivingArea"].isna() | (working["LivingArea"] <= 0)
    if "DaysOnMarket" in working.columns:
        working["DaysOnMarket_invalid_flag"] = working["DaysOnMarket"].isna() | (working["DaysOnMarket"] < 0)
    if "BedroomsTotal" in working.columns:
        working["BedroomsTotal_invalid_flag"] = working["BedroomsTotal"].isna() | (working["BedroomsTotal"] < 0)
    if "BathroomsTotalInteger" in working.columns:
        working["BathroomsTotalInteger_invalid_flag"] = (
            working["BathroomsTotalInteger"].isna() | (working["BathroomsTotalInteger"] < 0)
        )

    if {"ListingContractDate", "CloseDate"}.issubset(working.columns):
        working["listing_after_close_flag"] = working["ListingContractDate"] > working["CloseDate"]
    else:
        working["listing_after_close_flag"] = False

    if {"PurchaseContractDate", "CloseDate"}.issubset(working.columns):
        working["purchase_after_close_flag"] = working["PurchaseContractDate"] > working["CloseDate"]
    else:
        working["purchase_after_close_flag"] = False

    if {"ListingContractDate", "PurchaseContractDate"}.issubset(working.columns):
        purchase_before_listing = working["PurchaseContractDate"] < working["ListingContractDate"]
    else:
        purchase_before_listing = False
    working["negative_timeline_flag"] = (
        working["listing_after_close_flag"] | working["purchase_after_close_flag"] | purchase_before_listing
    )

    if {"Latitude", "Longitude"}.issubset(working.columns):
        lat = working["Latitude"]
        lon = working["Longitude"]
        working["geo_missing_coordinates_flag"] = lat.isna() | lon.isna()
        working["geo_zero_coordinates_flag"] = lat.eq(0) | lon.eq(0)
        working["geo_positive_longitude_flag"] = lon > 0
        working["geo_implausible_coordinates_flag"] = (~lat.between(32, 43)) | (~lon.between(-125, -114))
        working["geo_any_invalid_flag"] = (
            working["geo_missing_coordinates_flag"]
            | working["geo_zero_coordinates_flag"]
            | working["geo_positive_longitude_flag"]
            | working["geo_implausible_coordinates_flag"]
        )
    else:
        working["geo_missing_coordinates_flag"] = True
        working["geo_zero_coordinates_flag"] = False
        working["geo_positive_longitude_flag"] = False
        working["geo_implausible_coordinates_flag"] = True
        working["geo_any_invalid_flag"] = True

    missing_pct = working.isna().mean() * 100
    removable = [
        column
        for column, pct in missing_pct.items()
        if pct > 90 and column not in CORE_FIELDS and not column.endswith("_flag")
    ]
    if removable:
        working = working.drop(columns=removable)
        pd.DataFrame({"DroppedColumnsOver90PctNull": removable}).to_csv(
            CSV_DIR / f"{prefix}_dropped_columns_over_90pct_missing.csv", index=False
        )

    after_rows = len(working)
    print(f"{prefix}: rows before cleaning = {before_rows:,}")
    print(f"{prefix}: rows after cleaning  = {after_rows:,}")

    quality_summary = pd.DataFrame(
        {
            "Metric": [
                "Rows",
                "listing_after_close_flag",
                "purchase_after_close_flag",
                "negative_timeline_flag",
                "geo_missing_coordinates_flag",
                "geo_zero_coordinates_flag",
                "geo_positive_longitude_flag",
                "geo_implausible_coordinates_flag",
                "geo_any_invalid_flag",
            ],
            "Count": [
                len(working),
                int(working["listing_after_close_flag"].sum()),
                int(working["purchase_after_close_flag"].sum()),
                int(working["negative_timeline_flag"].sum()),
                int(working["geo_missing_coordinates_flag"].sum()),
                int(working["geo_zero_coordinates_flag"].sum()),
                int(working["geo_positive_longitude_flag"].sum()),
                int(working["geo_implausible_coordinates_flag"].sum()),
                int(working["geo_any_invalid_flag"].sum()),
            ],
        }
    )
    quality_summary.to_csv(CSV_DIR / f"{prefix}_data_quality_summary.csv", index=False)
    working.to_csv(CSV_DIR / f"{prefix}_cleaned_dataset.csv", index=False)
    return working


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
        "Records": ("MarketPrice", "size"),
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


def add_school_districts(df: pd.DataFrame, district_source: str = SCHOOL_DISTRICT_GEOJSON_URL) -> pd.DataFrame:
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
        if str(district_source).startswith(("http://", "https://")):
            with urlopen(district_source) as response:
                payload = response.read()
            with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as temp_file:
                temp_file.write(payload)
                temp_path = temp_file.name
            try:
                districts = gpd.read_file(temp_path)
            finally:
                Path(temp_path).unlink(missing_ok=True)
        else:
            districts = gpd.read_file(district_source)
    except Exception as exc:
        print(f"School district join unavailable: {exc}")
        return working

    if getattr(districts, "crs", None) is not None:
        districts = districts.to_crs("EPSG:4326")

    if "DistrictType" in districts.columns:
        districts = districts[districts["DistrictType"].astype(str).str.casefold() == "unified"].copy()

    if districts.empty:
        print("Skipping school district join; no unified district polygons were found.")
        return working

    points = gpd.GeoDataFrame(
        working.loc[valid_mask].copy(),
        geometry=gpd.points_from_xy(
            working.loc[valid_mask, "Longitude"],
            working.loc[valid_mask, "Latitude"],
        ),
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(points, districts, how="left", predicate="within")
    if "DistrictName" in joined.columns:
        working.loc[valid_mask, "DistrictName"] = joined["DistrictName"].values
    else:
        working.loc[valid_mask, "DistrictName"] = np.nan

    working["SchoolDistrict"] = working.get("DistrictName")
    return working


def add_iqr_flags(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    bounds_rows = []
    invalid_flag_columns: list[str] = []

    for column in columns:
        if column not in working.columns:
            continue

        values = pd.to_numeric(working[column], errors="coerce")
        values = values.replace([np.inf, -np.inf], np.nan)
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        flag_column = f"{column}_IQRFlag"
        invalid_column = f"{column}_Invalid"
        invalid_mask = values.isna()
        if column in {"ClosePrice", "MarketPrice", "LivingArea"}:
            invalid_mask = invalid_mask | (values <= 0)
        if column == "DaysOnMarket":
            invalid_mask = invalid_mask | (values < 0)
        working[invalid_column] = invalid_mask
        working[flag_column] = values.notna() & ((values < lower) | (values > upper))
        invalid_flag_columns.append(invalid_column)

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

    if invalid_flag_columns:
        working["AnyInvalidFlag"] = working[invalid_flag_columns].any(axis=1)
    else:
        working["AnyInvalidFlag"] = False

    bounds = pd.DataFrame(bounds_rows).round(2)
    return working, bounds


def week7_filtered_outputs(df: pd.DataFrame, prefix: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    analysis = df.copy()
    if "ClosePrice" in analysis.columns and (pd.to_numeric(analysis["ClosePrice"], errors="coerce") > 0).any():
        price_field = "ClosePrice"
    elif "MarketPrice" in analysis.columns:
        price_field = "MarketPrice"
    else:
        price_field = "ClosePrice"

    if price_field in analysis.columns:
        analysis = analysis[analysis[price_field].notna() & (analysis[price_field] > 0)].copy()

    flagged, bounds = add_iqr_flags(analysis, [price_field, "LivingArea", "DaysOnMarket"])
    clean = flagged[~flagged["AnyIQRFlag"] & ~flagged["AnyInvalidFlag"]].copy()

    comparison = pd.DataFrame(
        {
            "Metric": [
                "Records",
                f"Median{price_field}",
                "MedianLivingArea",
                "MedianDaysOnMarket",
                "MedianPriceRatio",
                "MedianPPSF",
            ],
            "BeforeFiltering": [
                len(flagged),
                flagged[price_field].median() if price_field in flagged.columns else np.nan,
                flagged["LivingArea"].median() if "LivingArea" in flagged.columns else np.nan,
                flagged["DaysOnMarket"].median() if "DaysOnMarket" in flagged.columns else np.nan,
                flagged["CloseToOriginalListRatio"].median() if "CloseToOriginalListRatio" in flagged.columns else np.nan,
                flagged["PricePerSqFt"].median() if "PricePerSqFt" in flagged.columns else np.nan,
            ],
            "AfterFiltering": [
                len(clean),
                clean[price_field].median() if price_field in clean.columns else np.nan,
                clean["LivingArea"].median() if "LivingArea" in clean.columns else np.nan,
                clean["DaysOnMarket"].median() if "DaysOnMarket" in clean.columns else np.nan,
                clean["CloseToOriginalListRatio"].median() if "CloseToOriginalListRatio" in clean.columns else np.nan,
                clean["PricePerSqFt"].median() if "PricePerSqFt" in clean.columns else np.nan,
            ],
        }
    )

    flagged.to_csv(CSV_DIR / f"{prefix}_week7_full_flagged.csv", index=False)
    clean.to_csv(CSV_DIR / f"{prefix}_week7_clean_filtered.csv", index=False)
    bounds.to_csv(CSV_DIR / f"{prefix}_week7_iqr_bounds.csv", index=False)
    comparison.to_csv(CSV_DIR / f"{prefix}_week7_filter_comparison.csv", index=False)

    if prefix == "CRMLSSold":
        flagged.to_csv(CSV_DIR / "week7_full_flagged_dataset.csv", index=False)
        clean.to_csv(CSV_DIR / "week7_clean_filtered_dataset.csv", index=False)
        bounds.to_csv(CSV_DIR / "week7_iqr_bounds.csv", index=False)
        comparison.to_csv(CSV_DIR / "week7_filter_comparison.csv", index=False)

    print(f"\n{prefix} Week 7 IQR bounds")
    print(bounds)
    print(f"\n{prefix} Week 7 filter comparison")
    print(comparison)
    return flagged, clean, comparison


def save_sample_output(df: pd.DataFrame, prefix: str) -> None:
    preferred_columns = [
        "PropertyType",
        "PropertySubType",
        "CountyOrParish",
        "MLSAreaMajor",
        "ClosePrice",
        "MarketPrice",
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


def save_feed_outputs(df: pd.DataFrame, prefix: str, include_school_districts: bool) -> pd.DataFrame:
    working = clean_dataset(df, prefix)
    working = engineer_metrics(working)
    if include_school_districts:
        working = add_school_districts(working)

    working.to_csv(CSV_DIR / f"{prefix}_combined_engineered.csv", index=False)

    flagged, clean, comparison = week7_filtered_outputs(working, prefix)

    print(f"\n{prefix} saved outputs")
    print(f"Full flagged rows: {len(flagged):,}")
    print(f"Clean filtered rows: {len(clean):,}")
    return working


def run_feed(prefix: str, date_column: str) -> pd.DataFrame:
    df = read_monthly_feed(prefix)
    df["SourceFeed"] = prefix
    df["YearMonth"] = pd.to_datetime(df[date_column], errors="coerce").dt.to_period("M")
    return df


def main(include_school_districts: bool = True) -> None:
    sold_raw = run_feed("CRMLSSold", "CloseDate")
    listing_raw = run_feed("CRMLSListing", "ListingContractDate")

    sold_raw.to_csv(CSV_DIR / "CRMLSSold_combined_all_propertytypes.csv", index=False)
    listing_raw.to_csv(CSV_DIR / "CRMLSListing_combined_all_propertytypes.csv", index=False)

    sold = filter_residential(sold_raw, "CRMLSSold")
    listing = filter_residential(listing_raw, "CRMLSListing")

    sold.to_csv(CSV_DIR / "CRMLSSold_combined_residential.csv", index=False)
    listing.to_csv(CSV_DIR / "CRMLSListing_combined_residential.csv", index=False)

    dataset_structure_reports(sold, "CRMLSSold")
    dataset_structure_reports(listing, "CRMLSListing")

    numeric_distribution_review(sold, "CRMLSSold")
    numeric_distribution_review(listing, "CRMLSListing")

    suggested_question_summary(sold, "CRMLSSold")
    suggested_question_summary(listing, "CRMLSListing")

    mortgage_monthly = fetch_fred_mortgage_monthly()
    sold = enrich_with_mortgage_rate(sold, "CRMLSSold", "CloseDate", mortgage_monthly)
    listing = enrich_with_mortgage_rate(listing, "CRMLSListing", "ListingContractDate", mortgage_monthly)

    sold = save_feed_outputs(sold, "CRMLSSold", include_school_districts)
    listing = save_feed_outputs(listing, "CRMLSListing", include_school_districts)

    combined = pd.concat([sold, listing], ignore_index=True, sort=False)

    print("\nWeek 6 numeric summary (sold feed)")
    print(summarize_numeric(sold, ["ClosePrice", "OriginalListPrice", "LivingArea", "DaysOnMarket", "PricePerSqFt", "PriceRatio"]))

    save_sample_output(sold, "CRMLSSold")
    save_sample_output(listing, "CRMLSListing")

    segment_analysis(combined)

    combined.to_csv(CSV_DIR / "CRMLS_combined_engineered.csv", index=False)

    print("\nSaved datasets")
    print(f"Sold rows: {len(sold):,}")
    print(f"Listing rows: {len(listing):,}")
    print(f"Combined rows: {len(combined):,}")


if __name__ == "__main__":
    main()