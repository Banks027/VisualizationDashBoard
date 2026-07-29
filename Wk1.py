if last_month == 0:
    last_month = 12
    year -= 1


def valid_file(filename):
    stem = filename.stem

    # Match filenames like CRMLSSold202606 or CRMLSListing202401
    match = re.search(r"(\d{4})(\d{2})$", stem)

    if not match:
        return False

    file_year = int(match.group(1))
    file_month = int(match.group(2))

    if file_year < START_YEAR:
        return False

    if file_year > year:
        return False

    if file_year == year and file_month > last_month:
        return False

    return True


def combine_files(prefix):

    property_column = COLUMN_INDEX[prefix]

    combined = []
    header = None

    files = sorted(DATA_FOLDER.glob(f"{prefix}*.csv"))

    print(f"\n{prefix}")
    print("----------------------------")

    total_rows_before = 0

    for file in files:

        if not valid_file(file):
            continue

        with file.open("r", newline="", encoding="utf-8") as f:

            reader = csv.reader(f)

            file_header = next(reader)

            if header is None:
                header = file_header

            rows = list(reader)

            print(f"{file.name}: {len(rows)} rows")

            total_rows_before += len(rows)

            combined.extend(rows)

    # Row count after concatenation
    print(f"\nRows before concatenation: {total_rows_before}")
    print(f"Rows after concatenation:  {len(combined)}")

    before_filter = len(combined)

    residential = [
        row
        for row in combined
        if len(row) > property_column
        and row[property_column].strip() == "Residential"
    ]

    after_filter = len(residential)

    print(f"Rows before Residential filter: {before_filter}")
    print(f"Rows after Residential filter:  {after_filter}")

    output = DATA_FOLDER / f"{prefix}_Combined_Residential.csv"

    with output.open("w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow(header)

        writer.writerows(residential)

    print(f"Saved: {output.name}")



if __name__ == "__main__":
    combine_files("CRMLSListing")
    combine_files("CRMLSSold")
    
