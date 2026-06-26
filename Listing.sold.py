import csv
from pathlib import Path


def read_csv_file(file_path, file_name):
    file_path = Path(file_path)
    filtered_rows = []

    try:
        pattern = f"{file_name}*.csv"
        for csv_file in file_path.glob(pattern):  # goes through all files in the directory that match the pattern
            if csv_file.name.endswith("_filtered.csv"):
                continue

            with csv_file.open("r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and len(row) > 10 and row[10].strip() == "Residential":
                        filtered_rows.append(row)
        return filtered_rows
    except FileNotFoundError:
        print("File not found. Please check the file path and try again.")
        print(file_path)
        return filtered_rows
    except PermissionError:
        print("Please check the file permissions and try again.")
        return filtered_rows


def print_csv_file(file_path, file_name):
    rows = read_csv_file(file_path, file_name)
    for row in rows:
        print(",".join(row)) #prints all the rows in the filtered list as a single string, with each value separated by a comma
    return rows


def create_csv_file(file_path, file_name):
    rows = read_csv_file(file_path, file_name)
    output_path = file_path / f"{file_name}_filtered.csv"
    print(f"Filtered rows written to {output_path}")
    try:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerows(rows)
            #make sure all records are on their own rows
        print(f"Filtered rows written to {output_path}")
    except PermissionError:
        print("Please check the write permissions and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    file_path = Path("C:/Users/Viv/Documents/Career readiness/internships/IDX exchange/csv")

    for prefix in ("CRMLSListing", "CRMLSSold"):
        print_csv_file(file_path, prefix)
        create_csv_file(file_path, prefix)
