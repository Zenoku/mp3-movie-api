import logging
import pandas as pd

logger = logging.getLogger(__name__)

def remove_duplicates(df):
    """Remove duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    logger.debug(f"{before - len(df)} rows removed")
    return df


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        before = len(df)
        df = df.dropna()
        logger.debug(f"{before - len(df)} rows removed")
        return df
    elif axis == "columns":
        before = df.shape[1]
        df = df.dropna(axis = 1)
        logger.debug(f"{before - df.shape[1]} columns removed")
        return df
    else:
        logger.error(f"Unsupported axis: {axis}")
        raise ValueError(f"Unsupported axis: {axis}. Please use 'rows' or 'columns'")


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ["iqr", "zscore"]:
        logger.error(f"Method is not supported: {method}")
        raise ValueError(f"Method is not supported: {method}")
    
    for col in columns:
        if col not in df.columns:
            logger.warning(f"Column does not exist: {col}")
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning(f"Column is not numeric: {col}")
            continue
            
        rows_before = len(df)
        
        if method == "iqr":
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            df = df[(df[col] >= lower) & (df[col] <= upper)]
        
        elif method == "zscore":
            mean = df[col].mean()
            std = df[col].std()
            z_scores = (df[col] - mean) / std
            df = df[z_scores.abs() <= threshold]
            
        rows_removed = rows_before - len(df)
        
        report = {
            "Column": {col},
            "Method": {method},
            "Threshold": {threshold},
            "Rows removed": {rows_removed}
        }
        logger.debug(f"{report}")
    
    return df


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config["processing"]
    
    if processing.get("remove_duplicates", False):
        df = remove_duplicates(df)
    
    missing = processing.get("missing", {})
    if missing.get("enabled", False):
        df = handle_missing(df, axis = missing.get("axis", "rows"))
        
    outliers = processing.get("outliers", {})
    if outliers.get("enabled", False):
        df = remove_outliers(
            df,
            columns = outliers["columns"],
            method = outliers["method"],
            threshold = outliers["threshold"]
        )
    
    return df


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    return {
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": len(df_before) - len(df_after),
        "columns_before": df_before.shape[1],
        "columns_after": df_after.shape[1],
        "columns_removed": df_before.shape[1] - df_after.shape[1],
    }