"""
WordPress platform implementation.
"""
import os
import json
import requests
import urllib.parse
import secrets
from typing import Dict, Any, Optional, List

from .base import Platform


class WordPressPlatform(Platform):
    """
    Platform implementation for WordPress.

    This implementation supports both:
    1. WordPress.com sites using OAuth2 authentication
    2. Self-hosted WordPress sites using Basic Auth or Application Passwords
    """

    def __init__(
        self,
        site_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        application_password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        user_id: Optional[int] = None,
        use_oauth: bool = False
    ):
        """
        Initialize the WordPress platform.

        Args:
            site_url: URL of your WordPress site (e.g., 'https://example.com')
            username: WordPress username (for Basic Auth or Application Passwords)
            password: WordPress password (for Basic Auth)
            application_password: WordPress application password (preferred over regular password)
            client_id: WordPress.com OAuth2 client ID
            client_secret: WordPress.com OAuth2 client secret
            access_token: WordPress.com OAuth2 access token
            redirect_uri: Redirect URI for OAuth2 authorization code flow
            user_id: User ID for retrieving credentials from the database
            use_oauth: Whether to use OAuth2 authentication (for WordPress.com sites)

        If any of the parameters are None, they will be read from environment variables:
        - WORDPRESS_SITE_URL
        - WORDPRESS_USERNAME
        - WORDPRESS_PASSWORD
        - WORDPRESS_APP_PASSWORD
        - WORDPRESS_CLIENT_ID
        - WORDPRESS_CLIENT_SECRET
        - WORDPRESS_ACCESS_TOKEN
        - WORDPRESS_REDIRECT_URI

        For self-hosted WordPress sites:
        - Provide site_url, username, and either password or application_password

        For WordPress.com sites:
        - Set use_oauth=True
        - Provide client_id, client_secret, and redirect_uri for OAuth2 flow
        - Or provide access_token for direct API access
        """
        # Basic credentials
        self.site_url = site_url or os.environ.get('WORDPRESS_SITE_URL')
        self.username = username or os.environ.get('WORDPRESS_USERNAME')
        self.password = password or os.environ.get('WORDPRESS_PASSWORD')
        self.application_password = application_password or os.environ.get('WORDPRESS_APP_PASSWORD')

        # OAuth2 credentials
        self.client_id = client_id or os.environ.get('WORDPRESS_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('WORDPRESS_CLIENT_SECRET')
        self.access_token = access_token or os.environ.get('WORDPRESS_ACCESS_TOKEN')
        self.redirect_uri = redirect_uri or os.environ.get('WORDPRESS_REDIRECT_URI')

        # User ID for database credentials
        self.user_id = user_id

        # Whether to use OAuth2 authentication
        self.use_oauth = use_oauth

        # Session and authentication state
        self.session = requests.Session()
        self.authenticated = False
        self.blog_id = os.environ.get('WORDPRESS_BLOG_ID')
        self.blog_url = os.environ.get('WORDPRESS_SITE_URL')

        # Store last error
        self.last_error = None

        # If user_id is provided, try to load credentials from the database
        if self.user_id:
            self._load_credentials_from_db()

        # Validate credentials based on authentication method
        if self.use_oauth:
            # For OAuth2, we need either access_token or (client_id, client_secret, redirect_uri)
            if not self.access_token and not (self.client_id and self.client_secret):
                raise ValueError("WordPress OAuth2 credentials are missing. Provide either access_token or (client_id, client_secret).")

            # Set API URL for WordPress.com
            self.api_url = "https://public-api.wordpress.com/rest/v1.1"
        else:
            # For Basic Auth or Application Passwords, we need site_url and credentials
            if not self.site_url:
                raise ValueError("WordPress site URL is missing")

            if not (self.application_password or self.password) and not self.user_id:
                raise ValueError("WordPress credentials are missing. Provide either application password, regular password, or user_id.")

            # Set API URL for self-hosted WordPress
            self.api_url = f"{self.site_url}/wp-json/wp/v2"

    def _load_credentials_from_db(self):
        """
        Load credentials from the database.
        """
        try:
            from ..database.setup import get_session, close_session
            from ..database.models import PlatformCredential

            session = get_session()
            try:
                credential = session.query(PlatformCredential).filter_by(
                    user_id=self.user_id,
                    platform='wordpress'
                ).first()

                if credential:
                    # Check if the token is expired
                    if credential.expires_at and credential.is_expired():
                        self.last_error = "WordPress access token has expired. Please reconnect your account."
                        return

                    # Parse the access token
                    if credential.token_type == 'oauth2':
                        # For OAuth2, the access_token field contains the actual token
                        self.access_token = credential.access_token
                        self.use_oauth = True
                        self.api_url = "https://public-api.wordpress.com/rest/v1.1"

                        # # First try to get blog_id and blog_url from token_data
                        # if credential.token_data:
                        #     try:
                        #         token_data = json.loads(credential.token_data)
                        #         self.blog_id = token_data.get('blog_id')
                        #         self.blog_url = token_data.get('blog_url')
                        #     except json.JSONDecodeError:
                        #         pass
                        #
                        # # If not found in token_data, try to extract from scope as fallback
                        # if not self.blog_id and credential.scope:
                        #     scope_parts = credential.scope.split(',')
                        #     for part in scope_parts:
                        #         if part.startswith('blog_id:'):
                        #             self.blog_id = part.split(':')[1]
                        #         elif part.startswith('blog_url:'):
                        #             self.blog_url = part.split(':')[1]

            finally:
                close_session(session)
        except Exception as e:
            self.last_error = f"Error loading WordPress credentials from database: {str(e)}"
            print(self.last_error)

    def authenticate(self) -> bool:
        """
        Authenticate with WordPress.

        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            if self.use_oauth:
                # For OAuth2, we use the access token
                if not self.access_token:
                    self.last_error = "WordPress OAuth2 access token is missing"
                    return False

                # Set up headers with the access token
                headers = {
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                }

                # Test authentication by making a request to the /me endpoint
                response = self.session.get(
                    f"{self.api_url}/me",
                    headers=headers
                )

                if response.status_code == 200:
                    # Store the headers for future requests
                    self.session.headers.update(headers)
                    self.authenticated = True

                    # Extract user info
                    user_info = response.json()
                    if 'ID' in user_info:
                        self.user_id_value = user_info['ID']

                    # If we don't have a blog ID yet, try to get it from the user info
                    # if not self.blog_id and 'primary_blog' in user_info:
                    #     self.blog_id = user_info['primary_blog']
                    #
                    # # If we don't have a blog URL yet, try to get it from the user info
                    # if not self.blog_url and 'primary_blog_url' in user_info:
                    #     self.blog_url = user_info['primary_blog_url']

                    return True
                else:
                    error_msg = f"WordPress OAuth2 authentication failed: {response.status_code} - {response.text}"

                    # Add more specific error messages based on status code
                    if response.status_code == 401:
                        error_msg += "\nYour access token may be invalid or expired."
                    elif response.status_code == 403:
                        error_msg += "\nYour access token doesn't have the necessary permissions."

                    self.last_error = error_msg
                    print(error_msg)
                    return False

        except Exception as e:
            error_msg = f"WordPress authentication failed: {str(e)}"
            self.last_error = error_msg
            print(error_msg)
            return False

    def is_authenticated(self) -> bool:
        """
        Check if the platform is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        # If we haven't checked authentication yet, do it now
        if not self.authenticated:
            return self.authenticate()

        return self.authenticated

    def get_authorization_url(self, scopes: Optional[List[str]] = None, state: Optional[str] = None, blog: Optional[str] = None) -> str:
        """
        Generate the authorization URL for the OAuth 2.0 authorization code flow.

        Args:
            scopes: List of scopes to request (defaults to ['global'])
            state: Optional state parameter for CSRF protection
            blog: Optional blog URL or ID to scope the authorization to

        Returns:
            Authorization URL to redirect the user to
        """
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Client ID and redirect URI are required for authorization")

        # Default scopes if none provided
        if not scopes:
            scopes = ['global']

        # Build the authorization URL
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(scopes)
        }

        # Add state parameter if provided
        if state:
            params['state'] = state

        # Add blog parameter if provided
        if blog:
            params['blog'] = blog

        # Build the URL
        auth_url = f"https://public-api.wordpress.com/oauth2/authorize?{urllib.parse.urlencode(params)}"
        return auth_url

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token.

        Args:
            code: Authorization code received from WordPress.com

        Returns:
            Dictionary containing the access token and other information
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("Client ID, client secret, and redirect URI are required for token exchange")

        # Prepare the token request
        token_url = "https://public-api.wordpress.com/oauth2/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }

        # Make the request
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses

            # Parse the response
            token_data = response.json()
            # Store the access token
            self.access_token = token_data.get('access_token')
            self.use_oauth = True
            self.api_url = "https://public-api.wordpress.com/rest/v1.1"

            # Extract blog information
            # if 'blog_id' in token_data:
            #     self.blog_id = token_data['blog_id']
            # if 'blog_url' in token_data:
            #     self.blog_url = token_data['blog_url']

            # Reset authentication status
            self.authenticated = False

            return token_data
        except Exception as e:
            error_msg = f"Error exchanging code for token: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_msg += f"\nResponse: {e.response.text}"

            self.last_error = error_msg
            raise ValueError(error_msg)

    def _log(self, message: str):
        """
        Log a message.

        Args:
            message: Message to log
        """
        print(message)

    def update_post(self, post_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing post on WordPress.

        Args:
            post_id: ID of the post to update
            content: The updated post content (HTML supported)
            **kwargs: Additional parameters:
                - title: Post title (required)
                - status: Post status (default: 'publish', options: 'publish', 'draft', 'pending', 'private')
                - excerpt: Post excerpt
                - featured_media_id: ID of the featured image
                - categories: List of category IDs
                - tags: List of tag IDs

        Returns:
            Dictionary with information about the updated post

        Raises:
            ValueError: If not authenticated or if required parameters are missing
        """
        if not self.is_authenticated() and not self.authenticate():
            error_msg = "Not authenticated with WordPress"
            if self.last_error:
                error_msg += f": {self.last_error}"
            raise ValueError(error_msg)

        # Get required parameters
        title = kwargs.get('title')
        if not title:
            raise ValueError("Title is required for WordPress posts")

        # Get optional parameters
        status = kwargs.get('status', 'publish')
        excerpt = kwargs.get('excerpt', '')
        featured_media_id = kwargs.get('featured_media_id')
        categories = kwargs.get('categories', [])
        tags = kwargs.get('tags', [])

        # Map is_draft to status
        if kwargs.get('is_draft', False):
            status = 'draft'

        try:
            if self.use_oauth:
                # For WordPress.com OAuth2 API
                # Prepare post data for WordPress.com API
                post_data = {
                    "title": title,
                    "content": content,
                    "status": status,
                }

                # Add optional fields if provided
                if excerpt:
                    post_data["excerpt"] = excerpt
                if categories:
                    post_data["categories"] = categories
                if tags:
                    post_data["tags"] = tags

                # Determine the endpoint based on whether we have a blog ID
                if self.blog_id:
                    self._log(f"Updating post {post_id} on blog ID {self.blog_id}")
                    endpoint = f"{self.api_url}/sites/{self.blog_id}/posts/{post_id}"
                else:
                    self._log(f"Updating post {post_id} on default blog")
                    # If no blog ID, try to use the default blog
                    endpoint = f"{self.api_url}/sites/self/posts/{post_id}"

                # Update the post
                response = self.session.post(
                    endpoint,
                    json=post_data
                )


            if response.status_code in (200, 201):
                post_data = response.json()

                # Extract post ID and URL based on API type
                if self.use_oauth:
                    post_id = str(post_data.get('ID', 'unknown'))
                    post_link = post_data.get('URL', '')
                else:
                    post_id = str(post_data.get('id', 'unknown'))
                    post_link = post_data.get('link', f"{self.site_url}/?p={post_id}")

                return {
                    'platform': 'wordpress',
                    'id': post_id,
                    'url': post_link,
                    'status': 'draft' if status == 'draft' else 'published',
                    'updated': True
                }
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"

                # Add more specific error messages based on status code
                if response.status_code == 401:
                    error_msg += "\nAuthentication failed. Your credentials may be invalid or expired."
                elif response.status_code == 403:
                    error_msg += "\nYou don't have permission to update this post."
                elif response.status_code == 400:
                    error_msg += "\nBad request. Check that your post data is valid."
                elif response.status_code == 404:
                    error_msg += "\nPost not found. The post ID may be invalid or the post may have been deleted."

                self.last_error = error_msg
                return {
                    'platform': 'wordpress',
                    'status': 'error',
                    'error': error_msg
                }
        except Exception as e:
            error_msg = str(e)
            self.last_error = error_msg
            return {
                'platform': 'wordpress',
                'status': 'error',
                'error': error_msg
            }

    def publish(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Publish a post to WordPress.

        Args:
            content: The post content (HTML supported)
            **kwargs: Additional parameters:
                - title: Post title (required)
                - status: Post status (default: 'publish', options: 'publish', 'draft', 'pending', 'private')
                - excerpt: Post excerpt
                - featured_media_id: ID of the featured image
                - categories: List of category IDs
                - tags: List of tag IDs
                - content_id: ID of the content in the database (for checking if it's already published)

        Returns:
            Dictionary with information about the published post

        Raises:
            ValueError: If not authenticated or if required parameters are missing
        """
        if not self.is_authenticated() and not self.authenticate():
            error_msg = "Not authenticated with WordPress"
            if self.last_error:
                error_msg += f": {self.last_error}"
            raise ValueError(error_msg)

        # Get required parameters
        title = kwargs.get('title')
        if not title:
            raise ValueError("Title is required for WordPress posts")

        # Check if this content has already been published to WordPress
        content_id = kwargs.get('content_id')

        if content_id:
            try:
                # Import here to avoid circular imports
                from ..data_sources.database_source import DatabaseDataSource

                # Get the publishing history for this content
                data_source = DatabaseDataSource()
                history = data_source.get_publishing_history(content_id, 'wordpress')
                print(history)
                # If we have a publishing history with a post ID, update the post instead of creating a new one
                if history and history.get('platform_post_id'):
                    self._log(f"Content {content_id} has already been published to WordPress with post ID {history['platform_post_id']}. Updating post...")
                    return self.update_post(history['platform_post_id'], content, **kwargs)
            except Exception as e:
                # If there's an error checking the publishing history, log it and continue with creating a new post
                self._log(f"Error checking publishing history: {str(e)}")

        # Get optional parameters
        status = kwargs.get('status', 'publish')
        excerpt = kwargs.get('excerpt', '')
        featured_media_id = kwargs.get('featured_media_id')
        categories = kwargs.get('categories', [])
        tags = kwargs.get('tags', [])

        # Map is_draft to status
        if kwargs.get('is_draft', False):
            status = 'draft'

        try:
            if self.use_oauth:
                # For WordPress.com OAuth2 API
                # Prepare post data for WordPress.com API
                post_data = {
                    "title": title,
                    "content": content,
                    "status": status,
                }

                # Add optional fields if provided
                if excerpt:
                    post_data["excerpt"] = excerpt
                if categories:
                    post_data["categories"] = categories
                if tags:
                    post_data["tags"] = tags

                # Determine the endpoint based on whether we have a blog ID
                if self.blog_id:
                    print(f"Publishing to blog ID {self.blog_id}")
                    endpoint = f"{self.api_url}/sites/{self.blog_id}/posts/new"
                else:
                    print("Publishing to self-hosted WordPress")
                    # If no blog ID, try to use the default blog
                    endpoint = f"{self.api_url}/sites/self/posts/new"

                # Create the post
                response = self.session.post(
                    endpoint,
                    json=post_data
                )


            if response.status_code in (200, 201):
                post_data = response.json()

                # Extract post ID and URL based on API type
                if self.use_oauth:
                    post_id = str(post_data.get('ID', 'unknown'))
                    post_link = post_data.get('URL', '')


                return {
                    'platform': 'wordpress',
                    'id': post_id,
                    'url': post_link,
                    'status': 'draft' if status == 'draft' else 'published'
                }
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"

                # Add more specific error messages based on status code
                if response.status_code == 401:
                    error_msg += "\nAuthentication failed. Your credentials may be invalid or expired."
                elif response.status_code == 403:
                    error_msg += "\nYou don't have permission to create posts."
                elif response.status_code == 400:
                    error_msg += "\nBad request. Check that your post data is valid."

                self.last_error = error_msg
                return {
                    'platform': 'wordpress',
                    'status': 'error',
                    'error': error_msg
                }
        except Exception as e:
            error_msg = str(e)
            self.last_error = error_msg
            return {
                'platform': 'wordpress',
                'status': 'error',
                'error': error_msg
            }
