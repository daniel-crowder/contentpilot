"""
Base class for data sources.
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict, Any, Optional


class DataSource(ABC):
    """
    Abstract base class for all data sources.
    """

    @abstractmethod
    def get_content(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve content from the data source.

        Args:
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            DataFrame with content data
        """
        pass

    @staticmethod
    def validate_dataframe(df: pd.DataFrame) -> bool:
        """
        Validate that the DataFrame has the required columns.

        Required columns:
        - publish_date: Date to publish the content (YYYY-MM-DD)
        - platform: Platform to publish to (twitter, linkedin, substack, wordpress)
        - content: The content to publish
        - title: Title (required for Substack and WordPress, optional for others)

        Args:
            df: DataFrame to validate

        Returns:
            True if valid, False otherwise
        """
        required_columns = ['publish_date', 'platform', 'content']

        # Check if all required columns exist
        for col in required_columns:
            if col not in df.columns:
                return False

        # Check if title exists for Substack and WordPress entries
        if 'title' not in df.columns and ('substack' in df['platform'].values or 'wordpress' in df['platform'].values):
            return False

        return True
