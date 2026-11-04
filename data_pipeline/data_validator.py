import logging
import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.

    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Required column(s) missing: {missing_columns}")
        raise ValueError(f"Required column(s) missing: {missing_columns}")
    
    rows_before = len(df)
    
    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except ValueError:
                    # TODO: Log a warning and record this row's index.
                    logger.warning(f"Invalid numeric value in {col} at row {i}: {value}")
                    invalid_rows.append(i)
        
        # TODO: Remove the invalid rows.
        df = df.drop(index = invalid_rows)

        #convert to a numeric data type
        df[col] = pd.to_numeric(df[col])
    
    rows_after = len(df)
    logger.debug(f"Valid rows: {rows_after}, removed rows: {rows_before - rows_after}")
        
    return df