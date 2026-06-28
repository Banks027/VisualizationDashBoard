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
Column = SimpleNamespace(PropType =-1, ClosePrice=-1, LivingArea=-1,DaysOnMarket=-1)


# Inspect structure
prefix.columns
sold.head()
# Check property categories
sold['PropertyType'].unique()
# Filter residential
sold = sold[sold.PropertyType == 'Residential']
# Validate completeness



def AllCalcs(Catagory,List):
    return np.min(List), np.max(List), np.mean(List), np.median(List), np.percentile(List, 90)

def Typefiltering(Catagory,rows,Column,filtered_rows):
 
 for row in rows:
    if row and len(row) > Column.proptype and row[Column.proptype].strip() == "Residential": #ex. column is located at index 10 for property type in the csv file
               
                print_filtered_csv(file_path, file_name,Column,row)

  return filtered_rows         

def read_csv_file(file_path, file_name,Column):
    file_path = Path(file_path)
    filtered_rows = []
    List= [] #all elements of array are zero
    try:
        pattern = f"{file_name}*.csv"
        for csv_file in file_path.glob(pattern):  # goes through all files in the directory that match the pattern
            if csv_file.name.endswith("_filtered.csv") |csv_file.name.endswith("_calculated.csv") :
                continue #breaks loop and excludes

            with csv_file.open("r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                for row in reader:
                   
                   Typefiltering(Column.proptype,row,Column,filtered_rows) ##dunno if this is right
                   for prefix in (ClosePrice, LivingArea, DaysOnMarket):
                    #make code only print resdental properties. 
                    
                    # List= np.loadtxt("data.txt", dtype=int)
                    prefix= AllCalcs(prefix.Min, prefix.Max, prefix.Mean, prefix.median, prefix.percentiles)
                    prefix.isnull().sum() #It returns the total number of missing or null values (such as NaN or None) in a specific column or dataset named sold
                    prefix['PropertyType'].unique()
                    List.clear() #resets array list after done
 
                    #determine unique property types
                    # Null count summary table for columns above 90%
                  
                    #all saved to .csv

        
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

    for prefix in ("_Calcuations.csv", "_filtered.csv"):
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
                Column.PropType = 10  # property type column in the CSV file
                Column.ClosePrice=4
                Column.LivingArea= 11
                Column.DaysOnMarket= 13

            case "CRMLSSold":
                Column.PropType = 17
                Column.ClosePrice= 11  # one minus actual column number
                Column.LivingArea= 18
                Column.DaysOnMarket= 20

            case _:
                print(f"Column for {prefix} is not vaild. Please check the column index and try again.")
                continue

        if (Column>-1):      #need to double check this
            read_csv_file(file_path, prefix, Column)
           # create_csv_file(file_path, prefix, column)