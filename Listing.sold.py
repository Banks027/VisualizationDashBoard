import csv #package allows for reading and writing of csv files
from pathlib import Path #more compatible way to handle file paths across different operating systems


def read_csv_file(file_path, file_name):
    # Ensure file_path is a Path
    file_path = Path(file_path)
    try:
        # iterate over all csv files that start with the given file_name in the directory
        pattern = f"{file_name}*.csv"
        for csv_file in file_path.glob(pattern):
            with csv_file.open("r", newline="", encoding='utf-8') as file:
                content = csv.reader(file)
                
                for line in content:
                    if len(line) > 10 and line[10] == "Residential":  # filtering the listings to only show residential listings
                        print(",".join(line))
                        
                        #print("\n".join(line))  # print each field on its own line
                        #print()  # blank line between entries
                        # for row in csv.reader:
                           # print(",".join(row)) 
    except FileNotFoundError:
        print("File not found. Please check the file path and try again.")
        print(file_path)
    except PermissionError:
        print("Please check the file permissions and try again.")


def create_csv_file():
    # This function is a placeholder for creating a new CSV file.
    # Implementation can be added as needed.


  ## try: 
        with open(file_path + file_name, "a") as file:
            file.write("This is a new CSV file.\n")
            csv.writer(file).writerow(["Column1", "Column2", "Column3"])  # Example header row
            print("Creating a new CSV file...")

    ##except FileExistsError:
      ##  print("File already exists. Please choose a different name or delete the existing file.")
    ##except PermissionError:
      ##   print("Please check the file permissions and try again.")


file_path = Path("C:/Users/Viv/Documents/Career readyness/internships/IDX exchange/csv")
file_name = "CRMLSListing20"

# need to iterate through entire folder of csv files and read each file in the folder.

read_csv_file(file_path, file_name) # used for general listings
create_csv_file(file_path, file_name)
file_name = "CRMLS20Sold20"
read_csv_file(file_path, file_name) # used for sold listings
#create_csv_file