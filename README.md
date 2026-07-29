# Visualization Dashboard

## 
This program is able to take data from several `CRMLSListing20YYMM.csv` and `CRMLSSold20YYMM.csv`. Moreover this programs has checks in place that elimate invaild data (ex.negative listing price), which ensure data quaility. Addtionally, live data from St. Louis Federal Reserve (FRED) API and propertry latitude/longitudes are incorperated into the data sets.  


## Prerequisites

- Install `numpy' , `pandas`, and `geopands` into your Python IDE environment:
  ```bash
  pip install numpy pandas
  ```

   ```bash
  pip install geopandas
  ```
- Several files containing `CRMLSListing20YYMM.csv` and `CRMLSSold20YYMM.csv` are required.

## Directions

1. Press the **Run** button for your corresponding IDE.
2. All of the calcuated data will be outputted to the terminal

3. Moreover, the following files will be generated:
   - `CRMLSListing_filtered_residential.csv`
   - `CRMLSSold_filtered_residential.csv`
   - `CRMLSListing_calculated_summary.csv`
   - `CRMLSSold_calculated_summary.csv`
   - `invalid_coordinates.csv`
   - `CRMLSListing  _numeric_summary.csv`
   - `CRMLSSold_numeric_summary.csv`
   - `CRMLSListing _null_summary.csv`
   - `CRMLSSold_null_summary.csv`

  These contain a copy of the outputed content. 