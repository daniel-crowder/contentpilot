"""
Database data source implementation.
"""
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..database.setup import get_session, close_session
from ..database.models import Content
from .base import DataSource


class DatabaseDataSource(DataSource):
    """
    Data source that reads content from the database.
    """

    def __init__(self):
        """
        Initialize the database data source.
        """
        pass

    def get_content(self, start_date: Optional[str] = None, end_date: Optional[str] = None, include_drafts: bool = False) -> pd.DataFrame:
        """
        Retrieve content from the database.

        Args:
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_drafts: Whether to include draft content (default: False)

        Returns:
            DataFrame with content data
        """
        session = get_session()

        try:
            # Start with a query for content that hasn't been published yet
            query = session.query(Content).filter(
                Content.is_published == False
            )

            # Filter out drafts if not explicitly included
            if not include_drafts:
                query = query.filter(Content.is_draft == False)

            # Apply date filters if provided
            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(Content.publish_date >= start_date_obj)

            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(Content.publish_date <= end_date_obj)

            # Execute the query
            contents = query.all()

            # Convert to list of dictionaries
            content_dicts = [self._content_to_dict(content) for content in contents]

            # Convert to DataFrame
            df = pd.DataFrame(content_dicts)

            # Validate the DataFrame
            if not df.empty and not self.validate_dataframe(df):
                raise ValueError("Database content does not have the required columns")

            return df if not df.empty else pd.DataFrame(columns=['publish_date', 'platform', 'content', 'title', 'subtitle', 'url'])

        finally:
            close_session(session)

    def _content_to_dict(self, content: Content) -> Dict[str, Any]:
        """
        Convert a Content object to a dictionary.

        Args:
            content: Content object

        Returns:
            Dictionary representation of the content
        """
        return {
            'id': content.id,
            'publish_date': content.publish_date.strftime('%Y-%m-%d'),
            'platform': content.platform,
            'content': content.content,
            'title': content.title or '',
            'subtitle': content.subtitle or '',
            'url': content.url or '',
            'publish_time': content.publish_time or '09:00',
            'is_draft': content.is_draft
        }

    def mark_as_published(self, content_id: int, platform_post_id: str = None, platform_post_url: str = None, status: str = 'success', error_message: str = None) -> bool:
        """
        Mark content as published in the database.

        Args:
            content_id: ID of the content
            platform_post_id: ID of the post on the platform
            platform_post_url: URL of the post on the platform
            status: Status of the publishing (success, error)
            error_message: Error message if status is error

        Returns:
            True if successful, False otherwise
        """
        from ..database.models import PublishingHistory

        session = get_session()

        try:
            # Get the content
            content = session.query(Content).filter(Content.id == content_id).first()

            if not content:
                return False

            # Mark as published
            content.is_published = (status == 'success')

            # Create publishing history record
            history = PublishingHistory(
                content_id=content_id,
                platform=content.platform,
                status=status,
                platform_post_id=platform_post_id,
                platform_post_url=platform_post_url,
                error_message=error_message,
                published_at=datetime.utcnow()
            )

            session.add(history)
            session.commit()

            return True

        except Exception as e:
            session.rollback()
            print(f"Error marking content as published: {str(e)}")
            return False

        finally:
            close_session(session)

    def add_content(self, platform: str, content: str, publish_date: str, title: str = None, subtitle: str = None, url: str = None, publish_time: str = "09:00", author_id: int = None, team_id: int = None, is_draft: bool = True) -> int:
        """
        Add new content to the database.

        Args:
            platform: Platform to publish to (twitter, linkedin, substack)
            content: The content to publish
            publish_date: Date to publish the content (YYYY-MM-DD)
            title: Title (required for Substack, optional for others)
            subtitle: Subtitle (optional, for Substack)
            url: URL to share (optional, for LinkedIn)
            publish_time: Time to publish (HH:MM)
            author_id: ID of the author
            team_id: ID of the team
            is_draft: Whether this is a draft

        Returns:
            ID of the created content, or None if failed
        """
        session = get_session()

        try:
            # Convert publish_date to datetime
            publish_date_obj = datetime.strptime(publish_date, '%Y-%m-%d')

            # Create new content
            new_content = Content(
                platform=platform,
                content=content,
                title=title,
                subtitle=subtitle,
                url=url,
                publish_date=publish_date_obj,
                publish_time=publish_time,
                author_id=author_id,
                team_id=team_id,
                is_draft=is_draft,
                is_published=False
            )

            session.add(new_content)
            session.commit()

            return new_content.id

        except Exception as e:
            session.rollback()
            print(f"Error adding content: {str(e)}")
            return None

        finally:
            close_session(session)
