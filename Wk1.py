from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


SOURCE_DIR = Path("C:/Users/Viv/Documents/Career readiness/internships/IDX exchange/csv")
START_YEAR = 2024
START_MONTH = 1
PROPERTY_FILTER = "Residential"
PERCENTILES = (10, 25, 50, 75, 90)
TERMINAL_FLOAT_FORMAT = lambda value: f"{value:,.6f}"

# Step 1 – Fetch the mortgage rate data from FRED
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
mortgage = pd.read_csv(URL, parse_dates=['observation_date'])
mortgage.columns = ['date', 'rate_30yr_fixed']


# Reporting rules:
# 1. Build a combined dataset from all monthly files in the date range.
# 2. Report unique PropertyType values found before filtering.
# 3. Apply the Residential-only filter.
# 4. Print and save null-count, missing-value, and numeric distribution summaries.
# 5. Save the filtered dataset as a new CSV.
#hi

def most_recent_completed_month(today=None):
    today = today or date.today()
    first_day_of_current_month = date(today.year, today.month, 1)
    last_completed_month = first_day_of_current_month - pd.offsets.MonthBegin(1)
    return last_completed_month.year, last_completed_month.month


def month_range(start_year, start_month, end_year, end_month):
    start = pd.Period(f"{start_year:04d}-{start_month:02d}", freq="M")
    end = pd.Period(f"{end_year:04d}-{end_month:02d}", freq="M")
    for period in pd.period_range(start, end, freq="M"):
        yield period.year, period.month


def build_monthly_file_list(prefix, start_year, start_month, end_year, end_month):
    monthly_files = []
    for year, month in month_range(start_year, start_month, end_year, end_month):
        file_name = f"{prefix}{year:04d}{month:02d}.csv"
        file_path = SOURCE_DIR / file_name
        if file_path.exists():
            monthly_files.append(file_path)
    return monthly_files


def load_monthly_data(files):
    frames = []
    row_count_before_concat = 0

    for file_path in files:
        frame = pd.read_csv(file_path, low_memory=False)
        frames.append(frame)
        row_count_before_concat += len(frame)

    print(f"Row count before concatenation: {row_count_before_concat}")

    if frames:
        combined = pd.concat(frames, ignore_index=True)
    else:
        combined = pd.DataFrame()

    print(f"Row count after concatenation: {len(combined)}")
    return combined


def get_property_column(frame):
    if "PropertyType" not in frame.columns:
        raise KeyError("PropertyType column was not found in the combined dataset.")
    return "PropertyType"


def unique_property_types(frame, property_column):
    values = frame[property_column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return sorted(values.unique().tolist())


def filter_residential_only(frame, property_column):
    print(f"Filtering logic applied: keep rows where {property_column} equals {PROPERTY_FILTER}.")
    before_filter = len(frame)
    filtered = frame[frame[property_column].astype(str).str.strip() == PROPERTY_FILTER].copy()
    print(f"Row count before Residential filter: {before_filter}")
    print(f"Row count after Residential filter: {len(filtered)}")
    return filtered


def build_null_summary(frame):
    summary = pd.DataFrame({
        "column": frame.columns,
        "null_count": frame.isna().sum().values,
        "row_count": len(frame),
    })
    summary["null_percent"] = np.where(
        summary["row_count"] > 0,
        (summary["null_count"] / summary["row_count"]) * 100,
        0.0,
    )
    return summary[["column", "null_count", "null_percent"]]


def build_missing_value_report(null_summary):
    flagged = null_summary[null_summary["null_percent"] > 90].copy()
    flagged.insert(0, "flag", "above_90_percent_null")
    return flagged[["flag", "column", "null_count", "null_percent"]]


def build_numeric_distribution_summary(frame, fields):
    rows = []
    for field in fields:
        if field not in frame.columns:
            rows.extend([
                {"field": field, "metric": "min", "value": np.nan},
                {"field": field, "metric": "max", "value": np.nan},
                {"field": field, "metric": "mean", "value": np.nan},
                {"field": field, "metric": "median", "value": np.nan},
                {"field": field, "metric": "p10", "value": np.nan},
                {"field": field, "metric": "p25", "value": np.nan},
                {"field": field, "metric": "p50", "value": np.nan},
                {"field": field, "metric": "p75", "value": np.nan},
                {"field": field, "metric": "p90", "value": np.nan},
            ])
            continue

        values = pd.to_numeric(frame[field], errors="coerce").dropna()
        if values.empty:
            stats = {
                "min": np.nan,
                "max": np.nan,
                "mean": np.nan,
                "median": np.nan,
                "p10": np.nan,
                "p25": np.nan,
                "p50": np.nan,
                "p75": np.nan,
                "p90": np.nan,
            }
        else:
            percentiles = np.percentile(values, PERCENTILES)
            stats = {
                "min": values.min(),
                "max": values.max(),
                "mean": values.mean(),
                "median": values.median(),
                "p10": percentiles[0],
                "p25": percentiles[1],
                "p50": percentiles[2],
                "p75": percentiles[3],
                "p90": percentiles[4],
            }

        for metric, value in stats.items():
            rows.append({"field": field, "metric": metric, "value": value})

    return pd.DataFrame(rows)


def build_report(file_name, frame, filtered_frame):
    property_column = get_property_column(frame)
    unique_types = unique_property_types(frame, property_column)
    null_summary = build_null_summary(frame)
    missing_value_report = build_missing_value_report(null_summary)
    numeric_summary = build_numeric_distribution_summary(
        frame,
        ["ClosePrice", "LivingArea", "DaysOnMarket"],
    )

    print(f"Unique property types found for {file_name}: {unique_types}")

    report_rows = []
    report_rows.append({
        "section": "metadata",
        "item": "file_name",
        "metric": "value",
        "value": file_name,
    })
    report_rows.append({
        "section": "metadata",
        "item": "source_rows",
        "metric": "count",
        "value": len(frame),
    })
    report_rows.append({
        "section": "metadata",
        "item": "filtered_rows",
        "metric": "count",
        "value": len(filtered_frame),
    })
    report_rows.append({
        "section": "filtering_logic",
        "item": property_column,
        "metric": "rule",
        "value": f'keep rows where value equals "{PROPERTY_FILTER}"',
    })
    report_rows.append({
        "section": "unique_property_types",
        "item": property_column,
        "metric": "unique_values",
        "value": ", ".join(unique_types),
    })

    for _, row in null_summary.iterrows():
        report_rows.append({
            "section": "null_summary",
            "item": row["column"],
            "metric": "null_count",
            "value": row["null_count"],
        })
        report_rows.append({
            "section": "null_summary",
            "item": row["column"],
            "metric": "null_percent",
            "value": round(float(row["null_percent"]), 2),
        })

    for _, row in missing_value_report.iterrows():
        report_rows.append({
            "section": "missing_value_report",
            "item": row["column"],
            "metric": row["flag"],
            "value": round(float(row["null_percent"]), 2),
        })

    for _, row in numeric_summary.iterrows():
        report_rows.append({
            "section": "numeric_distribution",
            "item": row["field"],
            "metric": row["metric"],
            "value": row["value"],
        })

    report_frame = pd.DataFrame(report_rows)
    print("\nNull-count summary table:")
    print(null_summary.to_string(index=False, float_format=TERMINAL_FLOAT_FORMAT))
    print("\nMissing value report (columns above 90% null):")
    print(missing_value_report.to_string(index=False, float_format=TERMINAL_FLOAT_FORMAT))
    print("\nNumeric distribution summary:")
    print(numeric_summary.to_string(index=False, float_format=TERMINAL_FLOAT_FORMAT))
    return report_frame


def save_outputs(file_path, file_name, filtered_frame, report_frame):
    file_path = Path(file_path)
    file_path.mkdir(parents=True, exist_ok=True)

    filtered_output = file_path / f"{file_name}_filtered_residential.csv"
    report_output = file_path / f"{file_name}_calculated_summary.csv"

    filtered_frame.to_csv(filtered_output, index=False)
    report_frame.to_csv(report_output, index=False)

    print(f"\nFiltered dataset saved to {filtered_output}")
    print(f"Summary report saved to {report_output}")


def process_prefix(prefix):
    end_year, end_month = most_recent_completed_month()
    monthly_files = build_monthly_file_list(prefix, START_YEAR, START_MONTH, end_year, end_month)

    if not monthly_files:
        print(f"No monthly files found for {prefix}.")
        return

    print(
        f"Found {len(monthly_files)} monthly files for {prefix} "
        f"from {START_YEAR:04d}-{START_MONTH:02d} through {end_year:04d}-{end_month:02d}."
    )

    combined = load_monthly_data(monthly_files)
    if combined.empty:
        print(f"Combined dataset for {prefix} is empty.")
        return

    filtered = filter_residential_only(combined, get_property_column(combined))
    report_frame = build_report(prefix, combined, filtered)
    save_outputs(SOURCE_DIR, prefix, filtered, report_frame)
    return filtered

# Step 4 – Merge mortgage rates onto the combined MLS datasets
def fetch_mortgage_monthly_rates(url=URL):
    mortgage = pd.read_csv(url, parse_dates=["observation_date"])
    mortgage.columns = ["date", "rate_30yr_fixed"]
    mortgage["year_month"] = mortgage["date"].dt.to_period("M")
    mortgage_monthly = (
        mortgage.groupby("year_month", as_index=False)["rate_30yr_fixed"]
        .mean()
    )
    return mortgage_monthly


def merge_mortgage_rates(frame, mortgage_monthly, date_column, dataset_name):
    frame_with_key = frame.copy()
    frame_with_key["year_month"] = pd.to_datetime(
        frame_with_key[date_column],
        errors="coerce",
    ).dt.to_period("M")

    merged = frame_with_key.merge(mortgage_monthly, on="year_month", how="left")
    null_rate_count = int(merged["rate_30yr_fixed"].isnull().sum())
    print(f"{dataset_name} null rate count after merge: {null_rate_count}")

    if null_rate_count != 0:
        raise ValueError(
            f"{dataset_name} merge produced {null_rate_count} null rate values."
        )

    return merged


def save_enriched_outputs(file_path, sold_with_rates, listings_with_rates):
    file_path = Path(file_path)
    file_path.mkdir(parents=True, exist_ok=True)

    sold_output = file_path / "CRMLSSold_filtered_residential_with_rates.csv"
    listings_output = file_path / "CRMLSListing_filtered_residential_with_rates.csv"

    sold_with_rates.to_csv(sold_output, index=False)
    listings_with_rates.to_csv(listings_output, index=False)

    print(f"Enriched sold dataset saved to {sold_output}")
    print(f"Enriched listings dataset saved to {listings_output}")


if __name__ == "__main__":
    mortgage_monthly = fetch_mortgage_monthly_rates()
    sold = process_prefix("CRMLSSold")
    listings = process_prefix("CRMLSListing")

    if sold is None or listings is None:
        raise RuntimeError("Unable to build the sold and listings datasets for merging.")

    sold_with_rates = merge_mortgage_rates(sold, mortgage_monthly, "CloseDate", "Sold")
    listings_with_rates = merge_mortgage_rates(
        listings,
        mortgage_monthly,
        "ListingContractDate",
        "Listings",
    )

    print(
        sold_with_rates[
            ["CloseDate", "year_month", "ClosePrice", "rate_30yr_fixed"]
        ].head()
    )

    save_enriched_outputs(SOURCE_DIR, sold_with_rates, listings_with_rates)