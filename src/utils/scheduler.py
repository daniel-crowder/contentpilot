"""
Scheduler for publishing content.
"""
import time
import logging
import schedule
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable

from ..data_sources.base import DataSource
from ..platforms.base import Platform


class ContentScheduler:
    """
    Scheduler for publishing content to social media platforms.
    """

    def __init__(self, data_source: DataSource, platforms: Dict[str, Platform], logger: Optional[logging.Logger] = None):
        """
        Initialize the content scheduler.

        Args:
            data_source: Data source to get content from
            platforms: Dictionary of platforms to publish to (key: platform name, value: Platform instance)
            logger: Optional logger instance
        """
        self.data_source = data_source
        self.platforms = platforms
        self.logger = logger or logging.getLogger(__name__)
        self.running = False
        self.scheduler_thread = None

        # Validate platforms
        for platform_name, platform in self.platforms.items():
            if not isinstance(platform, Platform):
                raise ValueError(f"Invalid platform: {platform_name}")

    def _log(self, message: str, level: str = 'info'):
        """
        Log a message.

        Args:
            message: Message to log
            level: Log level (info, warning, error)
        """
        if level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        else:
            self.logger.debug(message)

    def _publish_content(self, row: pd.Series) -> Dict[str, Any]:
        """
        Publish content to the specified platform.

        Args:
            row: Row from the DataFrame containing content to publish

        Returns:
            Dictionary with information about the published content
        """
        platform_name = row['platform'].lower()
        content = row['content']

        # Check if we have the platform
        if platform_name not in self.platforms:
            self._log(f"Platform not found: {platform_name}", 'error')
            return {
                'platform': platform_name,
                'status': 'error',
                'error': f"Platform not found: {platform_name}"
            }

        platform = self.platforms[platform_name]

        # Prepare kwargs for the platform
        kwargs = {}

        # Add content ID if available (for checking if already published)
        if 'id' in row:
            kwargs['content_id'] = row['id']

        # Add title for Substack
        if platform_name == 'substack' and 'title' in row:
            kwargs['title'] = row['title']

            # Add subtitle if available
            if 'subtitle' in row:
                kwargs['subtitle'] = row['subtitle']

            # Add draft status for Substack if available
            if 'is_draft' in row:
                kwargs['is_draft'] = row['is_draft']

        # Add title for WordPress
        if platform_name == 'wordpress' and 'title' in row:
            kwargs['title'] = row['title']

            # Add excerpt if available (using subtitle as excerpt)
            if 'subtitle' in row:
                kwargs['excerpt'] = row['subtitle']

            # Add draft status for WordPress if available
            if 'is_draft' in row:
                kwargs['is_draft'] = row['is_draft']

        # Add URL if available
        if 'url' in row:
            kwargs['url'] = row['url']

        try:
            # Authenticate if needed
            if not platform.is_authenticated():
                self._log(f"Authenticating with {platform_name}...")
                if not platform.authenticate():
                    self._log(f"Authentication failed for {platform_name}", 'error')
                    return {
                        'platform': platform_name,
                        'status': 'error',
                        'error': 'Authentication failed'
                    }

            # Publish content
            self._log(f"Publishing to {platform_name}...")
            result = platform.publish(content, **kwargs)

            if result.get('status') == 'error':
                self._log(f"Error publishing to {platform_name}: {result.get('error')}", 'error')
            else:
                self._log(f"Successfully published to {platform_name}")

            return result
        except Exception as e:
            self._log(f"Error publishing to {platform_name}: {str(e)}", 'error')
            return {
                'platform': platform_name,
                'status': 'error',
                'error': str(e)
            }

    def schedule_pending_content(self, include_drafts: bool = False) -> List[Dict[str, Any]]:
        """
        Schedule content that is due to be published today.

        Args:
            include_drafts: Whether to include draft content (default: False)

        Returns:
            List of results for content that was published immediately
        """
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        # Get content for today and tomorrow
        try:
            df = self.data_source.get_content(start_date=today, end_date=tomorrow, include_drafts=include_drafts)
        except Exception as e:
            self._log(f"Error getting content: {str(e)}", 'error')
            return []

        if df.empty:
            self._log("No content to publish")
            return []

        results = []

        # Process each row
        for _, row in df.iterrows():
            publish_date = row['publish_date']

            # If the publish date is today, publish immediately
            if publish_date == today:
                self._log(f"Publishing content scheduled for today ({today})")
                result = self._publish_content(row)
                results.append(result)
            else:
                # Schedule for tomorrow at a specific time (default: 9:00 AM)
                publish_time = "09:00"
                if 'publish_time' in row:
                    publish_time = row['publish_time']

                self._log(f"Scheduling content for {publish_date} at {publish_time}")

                # Create a job for this specific content
                def job(row=row):
                    self._log(f"Publishing scheduled content for {publish_date} at {publish_time}")
                    self._publish_content(row)

                # Schedule the job
                schedule.every().day.at(publish_time).do(job)

        return results

    def _run_scheduler(self):
        """
        Run the scheduler in a loop.
        """
        self._log("Starting scheduler...")

        while self.running:
            schedule.run_pending()
            time.sleep(1)

        self._log("Scheduler stopped")

    def start(self):
        """
        Start the scheduler.
        """
        if self.running:
            self._log("Scheduler is already running")
            return

        self.running = True

        # Schedule daily check for new content
        schedule.every().day.at("00:01").do(self.schedule_pending_content)

        # Schedule initial content
        self.schedule_pending_content()

        # Start the scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()

        self._log("Scheduler started")

    def stop(self):
        """
        Stop the scheduler.
        """
        if not self.running:
            self._log("Scheduler is not running")
            return

        self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        # Clear all scheduled jobs
        schedule.clear()

        self._log("Scheduler stopped")
