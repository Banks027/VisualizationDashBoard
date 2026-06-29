from ast import List
import csv
from pathlib import Path
from re import match
import struct
from types import SimpleNamespace
import numpy as np
import pandas as pd

ClosePrice= SimpleNamespace(Column=-1,Min=0, Max=0,Mean=0,median=0, percentiles=0)
LivingArea= SimpleNamespace(Column=-1,Min=0, Max=0,Mean=0,median=0, percentiles=0)
DaysOnMarket= SimpleNamespace(Column=-1,Max=0,Mean=0,median=0, percentiles=0)
Column = SimpleNamespace(proptype=-1, closeprice=-1, livingarea=-1, daysonmarket=-1)


# Inspect structure
#prefix.columns
#sold.head()
# Check property categories
#sold['PropertyType'].unique()
# Filter residential
#sold = sold[sold.PropertyType == 'Residential']
# Validate completeness


def Write_Calcs(file_path, file_name,Column,rows):
    for prefix in (ClosePrice, LivingArea, DaysOnMarket):
        #maybe do calcs functionand then return them for writing

        prefix= AllCalcs(prefix.Min, prefix.Max, prefix.Mean, prefix.median, prefix.percentiles)
        NullColumns=prefix.isnull().sum() #It returns the total number of missing or null values (such as NaN or None) in a specific column or dataset named sold
        UniqueTypes=prefix['PropertyType'].unique()
        List.clear() #resets array list after done


def AllCalcs(Catagory,List):
    return np.min(List), np.max(List), np.mean(List), np.median(List), np.percentile(List, 90)

def Typefiltering(row, Column, filtered_rows):
    # Take a single CSV row, and append to filtered_rows if PropertyType == 'Residential'.
    try:
        if row and Column.proptype >= 0 and len(row) > Column.proptype and row[Column.proptype].strip() == "Residential":
            filtered_rows.append(row)
    except Exception:
        pass

    return filtered_rows

def read_csv_file(file_path, file_name,Column):
    file_path = Path(file_path)
    filtered_rows = []
    List= [] #all elements of array are zero
    try:
        if not file_path.exists():
            print(f"CSV folder does not exist: {file_path}")
            return filtered_rows
        pattern = f"{file_name}*.csv"
        for csv_file in file_path.glob(pattern):  # goes through all files in the directory that match the pattern
            name_l = csv_file.name.lower()
            if name_l.endswith("_filtered.csv") or name_l.endswith("_calculated.csv"):
                continue # exclude previously generated files

            with csv_file.open("r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                for row in reader:
                    filtered_rows = Typefiltering(row, Column, filtered_rows)

            # after reading this file, print any filtered rows found
            if filtered_rows:
                print(f"Found {len(filtered_rows)} residential rows in {csv_file.name}")
               # print_filtered_csv(file_path, file_name, Column, filtered_rows)

        # return collected filtered rows for the caller
        return filtered_rows

        
    except FileNotFoundError:
        print("File not found. Please check the file path and try again.")
        print(file_path)
        return filtered_rows
    except PermissionError:
        print("Please check the file permissions and try again.")
        return filtered_rows


def print_filtered_csv(file_path, file_name,Column,rows):
   
    # rows = read_csv_file(file_path, file_name,Column)
     for row in rows:
        print(",".join(row)) #prints all the rows in the filtered list as a single string, with each value separated by a comma
    # return rows


def create_csv_file(file_path, file_name,Column):
    rows = read_csv_file(file_path, file_name,Column)
    file_path = Path(file_path)
    if not file_path.exists():
        try:
            file_path.mkdir(parents=True, exist_ok=True)
            print(f"Created output directory: {file_path}")
        except Exception as e:
            print(f"Could not create output directory: {e}")
            return
    for prefix in ("_calculated.csv", "_filtered.csv"):
        output_path = Path(file_path) / f"{file_name}{prefix}"
 
        try:
            with output_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerows(rows)
                #make sure all records are on their own rows
            print(f"\nFiltered rows written to {output_path}")
        except PermissionError:
            print("Please check the write permissions and try again.")
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    file_path = Path("C:/Users/Viv/Documents/Career readiness/internships/IDX exchange/csv")

    for prefix in ("CRMLSListing", "CRMLSSold"):
        column = -1 #allows for Property type column be located in any column

        match prefix:
            case "CRMLSListing":
                Column.proptype = 10  # property type column in the CSV file
                Column.closeprice = 4
                Column.livingarea = 11
                Column.daysonmarket = 13

            case "CRMLSSold":
                Column.proptype = 17
                Column.closeprice = 11  # one minus actual column number
                Column.livingarea = 18
                Column.daysonmarket = 20

            case _:
                print(f"Column for {prefix} is not vaild. Please check the column index and try again.")
                continue

        if (Column.proptype > -1 and Column.closeprice > -1 and Column.livingarea > -1 and Column.daysonmarket > -1):
            create_csv_file(file_path, prefix, Column)
           # create_csv_file(file_path, prefix, column)