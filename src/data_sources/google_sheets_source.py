"""
Google Sheets data source implementation.
"""
import os
import pandas as pd
from typing import Optional, List
from datetime import datetime

import google.auth
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import DataSource


class GoogleSheetsDataSource(DataSource):
    """
    Data source that reads content from a Google Sheet.
    """
    
    def __init__(self, sheet_id: str, range_name: str = 'A1:Z1000', credentials_file: Optional[str] = None):
        """
        Initialize the Google Sheets data source.
        
        Args:
            sheet_id: The ID of the Google Sheet
            range_name: The range to read (default: 'A1:Z1000')
            credentials_file: Path to the service account credentials JSON file.
                              If None, will try to use application default credentials.
        
        Raises:
            ValueError: If authentication fails or the sheet is not accessible
        """
        self.sheet_id = sheet_id
        self.range_name = range_name
        
        # Set up credentials
        try:
            if credentials_file:
                if not os.path.exists(credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {credentials_file}")
                self.credentials = Credentials.from_service_account_file(
                    credentials_file, 
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
            else:
                # Try to use application default credentials
                self.credentials, _ = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
        except Exception as e:
            raise ValueError(f"Failed to authenticate with Google Sheets: {str(e)}")
        
        # Test connection
        try:
            self._get_sheet_data()
        except Exception as e:
            raise ValueError(f"Failed to access Google Sheet: {str(e)}")
    
    def _get_sheet_data(self) -> List[List[str]]:
        """
        Get raw data from the Google Sheet.
        
        Returns:
            List of rows, where each row is a list of values
        """
        service = build('sheets', 'v4', credentials=self.credentials)
        sheet = service.spreadsheets()
        
        try:
            result = sheet.values().get(
                spreadsheetId=self.sheet_id,
                range=self.range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                raise ValueError("No data found in the Google Sheet")
                
            return values
        except HttpError as e:
            raise ValueError(f"Error accessing Google Sheet: {str(e)}")
    
    def get_content(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve content from the Google Sheet.
        
        Args:
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            DataFrame with content data
        """
        values = self._get_sheet_data()
        
        # First row is headers
        headers = values[0]
        data = values[1:]
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=headers)
        
        # Validate the DataFrame
        if not self.validate_dataframe(df):
            raise ValueError("Google Sheet does not have the required columns")
        
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