"""
X (Twitter) platform implementation.
"""
import os
import tweepy
from typing import Dict, Any, Optional

from .base import Platform


class TwitterPlatform(Platform):
    """
    Platform implementation for X (Twitter).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None
    ):
        """
        Initialize the Twitter platform.

        Args:
            api_key: Twitter API key (consumer key)
            api_secret: Twitter API secret (consumer secret)
            access_token: Twitter access token
            access_token_secret: Twitter access token secret

        If any of the parameters are None, they will be read from environment variables:
        - TWITTER_API_KEY
        - TWITTER_API_SECRET
        - TWITTER_ACCESS_TOKEN
        - TWITTER_ACCESS_TOKEN_SECRET
        """
        self.api_key = api_key or os.environ.get('TWITTER_API_KEY')
        self.api_secret = api_secret or os.environ.get('TWITTER_API_SECRET')
        self.access_token = access_token or os.environ.get('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = access_token_secret or os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

        self.client = None

        # Validate credentials
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            raise ValueError("Twitter API credentials are missing")

    def authenticate(self) -> bool:
        """
        Authenticate with the Twitter API.

        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            # Create client with appropriate permissions
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=True
            )

            # Test authentication by getting user info
            self.client.get_me()

            return True
        except Exception as e:
            print(f"Twitter authentication failed: {str(e)}")
            self.client = None
            return False

    def is_authenticated(self) -> bool:
        """
        Check if the platform is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return self.client is not None

    def publish(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Publish a tweet.

        Args:
            content: The tweet text
            **kwargs: Additional parameters (not used for Twitter)

        Returns:
            Dictionary with information about the published tweet

        Raises:
            ValueError: If not authenticated or if the tweet is too long
        """
        if not self.is_authenticated():
            raise ValueError("Not authenticated with Twitter")

        # Twitter has a 280 character limit
        if len(content) > 280:
            raise ValueError(f"Tweet is too long ({len(content)} characters). Maximum is 280 characters.")

        try:
            response = self.client.create_tweet(text=content)

            # Extract tweet ID from response
            tweet_id = response.data['id']

            return {
                'platform': 'twitter',
                'id': tweet_id,
                'url': f"https://twitter.com/user/status/{tweet_id}",
                'status': 'published'
            }
        except Exception as e:
            error_msg = str(e)

            # Check for permissions error
            if "403 Forbidden" in error_msg and "oauth1 app permissions" in error_msg:
                error_msg += "\n\nTo fix this issue, you need to configure your Twitter Developer App with the appropriate permissions:\n"
                error_msg += "1. Go to https://developer.twitter.com/en/portal/dashboard\n"
                error_msg += "2. Select your app\n"
                error_msg += "3. Go to 'App permissions' and ensure 'Read and Write' permissions are enabled\n"
                error_msg += "4. Go to 'Keys and tokens' and regenerate your access token and secret with the new permissions"

            return {
                'platform': 'twitter',
                'status': 'error',
                'error': error_msg
            }
