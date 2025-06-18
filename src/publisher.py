"""
Main module for the Social Media Content Publisher.
"""
import os
import sys
import argparse
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .data_sources.csv_source import CSVDataSource
from .data_sources.google_sheets_source import GoogleSheetsDataSource
from .data_sources.database_source import DatabaseDataSource
from .platforms.twitter import TwitterPlatform
from .platforms.linkedin import LinkedInPlatform
from .platforms.substack import SubstackPlatform
from .utils.scheduler import ContentScheduler
from .utils.logger import get_default_logger


def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.

    Args:
        config_file: Path to the configuration file

    Returns:
        Configuration dictionary
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, 'r') as f:
        return json.load(f)


def setup_data_source(config: Dict[str, Any]):
    """
    Set up the data source based on the configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured data source
    """
    source_type = config.get('source_type', '').lower()

    if source_type == 'csv':
        file_path = config.get('file_path')
        if not file_path:
            raise ValueError("CSV file path is missing in configuration")

        return CSVDataSource(file_path)

    elif source_type == 'google_sheets':
        sheet_id = config.get('sheet_id')
        range_name = config.get('range_name', 'A1:Z1000')
        credentials_file = config.get('credentials_file')

        if not sheet_id:
            raise ValueError("Google Sheet ID is missing in configuration")

        return GoogleSheetsDataSource(sheet_id, range_name, credentials_file)

    elif source_type == 'database':
        # Initialize database if needed
        from ..database.setup import init_db
        init_db()

        return DatabaseDataSource()

    else:
        raise ValueError(f"Unsupported data source type: {source_type}")


def setup_platforms(config: Dict[str, Any]):
    """
    Set up the platforms based on the configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary of configured platforms
    """
    platforms = {}

    # Set up Twitter platform if enabled
    if config.get('twitter', {}).get('enabled', False):
        twitter_config = config.get('twitter', {})
        platforms['twitter'] = TwitterPlatform(
            api_key=twitter_config.get('api_key'),
            api_secret=twitter_config.get('api_secret'),
            access_token=twitter_config.get('access_token'),
            access_token_secret=twitter_config.get('access_token_secret')
        )

    # Set up LinkedIn platform if enabled
    if config.get('linkedin', {}).get('enabled', False):
        linkedin_config = config.get('linkedin', {})
        platforms['linkedin'] = LinkedInPlatform(
            client_id=linkedin_config.get('client_id'),
            client_secret=linkedin_config.get('client_secret'),
            access_token=linkedin_config.get('access_token'),
            organization_id=linkedin_config.get('organization_id')
            # Note: user_id is not used here because this is a command-line utility
            # without a user context. It uses the access token from the config file.
        )

    # Set up Substack platform if enabled
    if config.get('substack', {}).get('enabled', False):
        substack_config = config.get('substack', {})
        platforms['substack'] = SubstackPlatform(
            publication_name=substack_config.get('publication_name'),
            email=substack_config.get('email'),
            password=substack_config.get('password'),
            cookie=substack_config.get('cookie')
        )

    return platforms


def main():
    """
    Main entry point for the application.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Social Media Content Publisher')
    parser.add_argument('--config', '-c', default='config.json', help='Path to configuration file')
    parser.add_argument('--publish-now', '-p', action='store_true', help='Publish content immediately without scheduling')
    parser.add_argument('--include-drafts', '-d', action='store_true', help='Include draft content when publishing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Set up logger
    logger = get_default_logger()

    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Set up data source
        logger.info("Setting up data source")
        data_source = setup_data_source(config)

        # Set up platforms
        logger.info("Setting up platforms")
        platforms = setup_platforms(config)

        if not platforms:
            logger.error("No platforms are enabled in the configuration")
            sys.exit(1)

        # Set up scheduler
        logger.info("Setting up content scheduler")
        scheduler = ContentScheduler(data_source, platforms, logger)

        if args.publish_now:
            # Publish content immediately
            logger.info("Publishing content immediately")
            if args.include_drafts:
                logger.info("Including draft content")
            results = scheduler.schedule_pending_content(include_drafts=args.include_drafts)

            # Print results
            for result in results:
                if result.get('status') == 'error':
                    logger.error(f"Error publishing to {result.get('platform')}: {result.get('error')}")
                else:
                    logger.info(f"Successfully published to {result.get('platform')}")
        else:
            # Start the scheduler
            logger.info("Starting scheduler")
            scheduler.start()

            # Keep the main thread running
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping scheduler")
                scheduler.stop()

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
