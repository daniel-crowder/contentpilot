"""
CSV data source implementation.
"""
import os
import pandas as pd
from datetime import datetime
from typing import Optional

from .base import DataSource


class CSVDataSource(DataSource):
    """
    Data source that reads content from a CSV file.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize the CSV data source.
        
        Args:
            file_path: Path to the CSV file
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is not a valid CSV
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        self.file_path = file_path
        
        # Try to read the file to validate it's a proper CSV
        try:
            df = pd.read_csv(file_path)
            if not self.validate_dataframe(df):
                raise ValueError("CSV file does not have the required columns")
        except Exception as e:
            raise ValueError(f"Invalid CSV file: {str(e)}")
    
    def get_content(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve content from the CSV file.
        
        Args:
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            DataFrame with content data
        """
        df = pd.read_csv(self.file_path)
        
        # Convert publish_date to datetime for filtering
        df['publish_date'] = pd.to_datetime(df['publish_date'])
        
        # Apply date filters if provided
        if start_date:
            start_date = pd.to_datetime(start_date)
            df = df[df['publish_date'] >= start_date]
        
        if end_date:
            end_date = pd.to_datetime(end_date)
            df = df[df['publish_date'] <= end_date]
        
        # Convert back to string format for consistency
        df['publish_date'] = df['publish_date'].dt.strftime('%Y-%m-%d')
        
        return df