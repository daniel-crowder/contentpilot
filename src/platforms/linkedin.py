"""
LinkedIn platform implementation.
"""
import os
import json
import requests
import mimetypes
import base64
import urllib.parse
from typing import Dict, Any, Optional, Tuple

from .base import Platform


class LinkedInPlatform(Platform):
    """
    Platform implementation for LinkedIn.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        organization_id: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        user_id: Optional[int] = None
    ):
        """
        Initialize the LinkedIn platform.

        Args:
            client_id: LinkedIn client ID
            client_secret: LinkedIn client secret
            access_token: LinkedIn access token
            organization_id: LinkedIn organization ID (for company posts)
            redirect_uri: Redirect URI for OAuth 2.0 authorization code flow
            user_id: ID of the user to get credentials for (if using database storage)

        If any of the parameters are None, they will be read from environment variables:
        - LINKEDIN_CLIENT_ID
        - LINKEDIN_CLIENT_SECRET
        - LINKEDIN_ACCESS_TOKEN
        - LINKEDIN_ORGANIZATION_ID
        - LINKEDIN_REDIRECT_URI

        Note on LinkedIn Authorization:
        To obtain the necessary credentials, follow these steps:
        1. Create a LinkedIn Developer App at https://www.linkedin.com/developers/
        2. Request the following OAuth scopes:
           - r_liteprofile: For reading basic profile information
           - w_member_social: For posting content on behalf of a member
           - r_organization_social: For reading organization social content (if posting as organization)
           - w_organization_social: For posting content on behalf of an organization (if posting as organization)
        3. Set up OAuth 2.0 settings in your LinkedIn app:
           - Add your redirect URI (e.g., http://localhost:5000/linkedin/callback)
           - Note your client ID and client secret
        4. Use the authorization code flow to obtain an access token
        5. If posting as an organization, obtain your organization ID
        """
        self.client_id = client_id or os.environ.get('LINKEDIN_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('LINKEDIN_CLIENT_SECRET')
        self.access_token = access_token or os.environ.get('LINKEDIN_ACCESS_TOKEN')
        self.organization_id = organization_id or os.environ.get('LINKEDIN_ORGANIZATION_ID')
        self.redirect_uri = redirect_uri or os.environ.get('LINKEDIN_REDIRECT_URI')
        self.user_id = user_id

        # Base API URL
        self.api_url = "https://api.linkedin.com/v2"

        # LinkedIn API version to use
        self.api_version = "202401"  # Using a stable API version

        # Store last error message
        self.last_error = None

        # Store user info
        self.user_info = None

        # Store user ID value
        self.user_id_value = None

        # Cache authentication status
        self._is_authenticated = None

        # Validate credentials
        if not all([self.client_id, self.client_secret]):
            raise ValueError("LinkedIn client ID and client secret are required")

        # For authorization code flow, redirect_uri is required
        if not self.access_token and not self.redirect_uri and not self.user_id:
            raise ValueError("Either an access token, a redirect URI, or a user ID is required for authentication")

        # Try to get credentials from database if user_id is provided and no access token
        # if not self.access_token and self.user_id:
        #     self._load_credentials_from_database()
        self._load_credentials_from_database()

    def _load_credentials_from_database(self):
        """
        Load LinkedIn credentials from the database for the current user.

        This method queries the PlatformCredential model to find LinkedIn credentials
        for the user specified by self.user_id. If found, it sets the access_token
        and checks if the token is expired.
        """
        try:
            # Import here to avoid circular imports
            from ..database.setup import get_session, close_session
            from ..database.models import PlatformCredential

            session = get_session()
            try:
                # Query for LinkedIn credentials for this user
                credential = session.query(PlatformCredential).filter(
                    PlatformCredential.user_id == self.user_id,
                    PlatformCredential.platform == 'linkedin'
                ).first()

                if credential:
                    # Check if the token is expired
                    if credential.expires_at and credential.is_expired():
                        self.last_error = "LinkedIn access token has expired. Please reconnect your account."
                        return

                    # Set the access token
                    self.access_token = credential.access_token

                    # Reset authentication status
                    self._is_authenticated = None

                    # Try to authenticate to get the user info and ID
                    # This will make an API call to LinkedIn to get the user info
                    # and extract the user ID
                    try:
                        self.authenticate()
                    except Exception as e:
                        print(f"Error authenticating with LinkedIn: {str(e)}")
                        # Even if authentication fails, we still have the access token
                        # so we can continue
            finally:
                close_session(session)
        except Exception as e:
            self.last_error = f"Error loading LinkedIn credentials from database: {str(e)}"

    def authenticate(self) -> bool:
        """
        Authenticate with the LinkedIn API.

        This method verifies that the access token is valid by making a request to the LinkedIn API.
        It also checks for the necessary permissions (scopes) required for posting content.

        Required scopes:
        - r_liteprofile: For reading basic profile information
        - w_member_social: For posting content on behalf of a member
        - r_organization_social: For reading organization social content (if posting as organization)
        - w_organization_social: For posting content on behalf of an organization (if posting as organization)

        Returns:
            True if authentication was successful, False otherwise
        """

        try:
            # Test authentication by getting profile info
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0',
                'LinkedIn-Version': self.api_version,
            }

            # Try to get user profile to verify token
            response = requests.get(
                f"{self.api_url}/me",  # Removed trailing slash for consistency
                headers=headers
            )

            if response.status_code == 200:
                self._is_authenticated = True

                # Store user info for potential use later
                self.user_info = response.json()

                # Extract and store the user ID
                if 'id' in self.user_info:
                    self.user_id_value = self.user_info['id']
                else:
                    # If 'id' is not directly in the response, try to find it in a nested structure
                    # Common LinkedIn API response structure might have it in different places
                    # This is a fallback mechanism
                    self.user_id_value = None

                    # Try to find id in common locations
                    if 'localizedFirstName' in self.user_info:  # This suggests it's a /me response
                        # For /me endpoint, the ID might be in the request URL or response headers
                        # As a fallback, we'll use the sub-resources to try to extract it
                        try:
                            # Make another request to get the profile
                            profile_response = requests.get(
                                f"{self.api_url}/me?projection=(id)",
                                headers=headers
                            )
                            if profile_response.status_code == 200:
                                profile_data = profile_response.json()
                                if 'id' in profile_data:
                                    self.user_id_value = profile_data['id']
                        except Exception as e:
                            print(f"Error getting LinkedIn profile ID: {str(e)}")

                # Check if we need to validate organization access
                if self.organization_id:
                    # Verify organization access
                    org_response = requests.get(
                        f"{self.api_url}/organizations/{self.organization_id}",
                        headers=headers
                    )

                    if org_response.status_code != 200:
                        error_msg = f"LinkedIn organization access failed: {org_response.text}"
                        print(error_msg)
                        self.last_error = error_msg
                        self._is_authenticated = False
                        return False

                return True
            else:
                error_msg = f"LinkedIn authentication failed: {response.text}"

                # Add more specific error messages based on status code
                if response.status_code == 401:
                    error_msg += "\nYour access token may be invalid or expired. LinkedIn access tokens typically expire after 60 days."
                elif response.status_code == 403:
                    error_msg += "\nYour access token doesn't have the necessary permissions. Ensure it has r_liteprofile and w_member_social scopes."

                print(error_msg)
                self.last_error = error_msg
                self._is_authenticated = False
                return False
        except Exception as e:
            error_msg = f"LinkedIn authentication failed: {str(e)}"
            print(error_msg)
            self.last_error = error_msg
            self._is_authenticated = False
            return False

    def is_authenticated(self) -> bool:
        """
        Check if the platform is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        # If we haven't checked authentication yet, do it now
        if self._is_authenticated is None:
            return self.authenticate()

        # Otherwise, return the cached result
        return self._is_authenticated

    def get_authorization_url(self, scopes: Optional[list] = None, state: Optional[str] = None) -> str:
        """
        Generate the authorization URL for the OAuth 2.0 authorization code flow.

        Args:
            scopes: List of scopes to request (defaults to r_liteprofile and w_member_social)
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect the user to
        """
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Client ID and redirect URI are required for authorization")

        # Default scopes if none provided
        if not scopes:
            #scopes = ['r_liteprofile', 'w_member_social']
            scopes = ['w_member_social']
        scopes = ['w_member_social', 'openid', 'profile', 'email', 'r_basicprofile', 'w_member_social']
        # Build the authorization URL
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes),
        }

        # Add state parameter if provided
        if state:
            params['state'] = state

        # Build the URL
        auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urllib.parse.urlencode(params)}"
        return auth_url

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token.

        Args:
            code: Authorization code received from LinkedIn

        Returns:
            Dictionary containing the access token and other information
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("Client ID, client secret, and redirect URI are required for token exchange")

        # Prepare the token request
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

        # Make the request
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses

            # Parse the response
            token_data = response.json()

            # Store the access token
            self.access_token = token_data.get('access_token')
            self._is_authenticated = None  # Reset authentication status

            return token_data
        except Exception as e:
            error_msg = f"Error exchanging code for token: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_msg += f"\nResponse: {e.response.text}"

            self.last_error = error_msg
            raise ValueError(error_msg)

    def get_token_refresh_instructions(self) -> str:
        """
        Get instructions for refreshing the LinkedIn access token.

        LinkedIn access tokens typically expire after 60 days. This method provides
        step-by-step instructions on how to obtain a new access token.

        Returns:
            String with instructions for refreshing the access token
        """
        instructions = """
LinkedIn Access Token Refresh Instructions:

1. Go to the LinkedIn Developer Portal: https://www.linkedin.com/developers/
2. Select your application
3. Go to the "Auth" tab
4. Under "OAuth 2.0 settings", click on "Generate Token"
5. Select the following scopes:
   - r_liteprofile: For reading basic profile information
   - w_member_social: For posting content on behalf of a member
   - r_organization_social: For reading organization social content (if posting as organization)
   - w_organization_social: For posting content on behalf of an organization (if posting as organization)
6. Click "Generate Access Token"
7. Copy the new access token and update your configuration

Note: LinkedIn access tokens typically expire after 60 days. You'll need to repeat this process when your token expires.
"""
        return instructions

    def _upload_image(self, image_path: str, image_description: str = '') -> Tuple[bool, str, Optional[str]]:
        """
        Upload an image to LinkedIn.

        Args:
            image_path: Path to the image file
            image_description: Optional description for the image

        Returns:
            Tuple containing:
            - Success flag (True if upload was successful)
            - Asset ID if successful, error message if not
            - Upload URL if successful, None if not
        """
        if not os.path.exists(image_path):
            return False, f"Image file not found: {image_path}", None

        # Determine file size and MIME type
        file_size = os.path.getsize(image_path)
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Step 1: Register the image upload
        register_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': self.api_version
        }

        register_data = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": "urn:li:person:me",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }

        try:
            register_response = requests.post(
                f"{self.api_url}/assets?action=registerUpload",
                headers=register_headers,
                json=register_data
            )

            if register_response.status_code != 200:
                return False, f"Failed to register image upload: {register_response.text}", None

            # Extract upload URL and asset ID
            register_data = register_response.json()
            asset = register_data.get('value', {}).get('asset', '')
            upload_url = register_data.get('value', {}).get('uploadMechanism', {}).get('com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest', {}).get('uploadUrl', '')

            if not asset or not upload_url:
                return False, "Failed to get upload URL or asset ID", None

            # Step 2: Upload the image
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()

            upload_headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': mime_type
            }

            upload_response = requests.put(
                upload_url,
                headers=upload_headers,
                data=image_data
            )

            if upload_response.status_code not in (200, 201):
                return False, f"Failed to upload image: {upload_response.text}", None

            return True, asset, upload_url

        except Exception as e:
            return False, f"Error uploading image: {str(e)}", None

    def publish(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Publish a post to LinkedIn.

        Args:
            content: The post text (max 3000 characters)
            **kwargs: Additional parameters:
                - title: Optional post title (max 150 characters)
                - subtitle: Optional post subtitle (max 150 characters)
                - url: Optional URL to share
                - image_path: Optional path to an image file to upload
                - image_description: Optional description for the image

        Returns:
            Dictionary with information about the published post

        Raises:
            ValueError: If not authenticated or if content exceeds character limits
        """
        if not self.is_authenticated():
            error_msg = "Not authenticated with LinkedIn"
            if self.last_error:
                error_msg += f": {self.last_error}"

            # Add token refresh instructions
            error_msg += "\n\n" + self.get_token_refresh_instructions()

            raise ValueError(error_msg)

        # Get optional parameters
        title = kwargs.get('title', '')
        subtitle = kwargs.get('subtitle', '')
        url = kwargs.get('url', '')
        image_path = kwargs.get('image_path', '')
        image_description = kwargs.get('image_description', '')

        # Enforce character limits
        if len(content) > 3000:
            raise ValueError(f"LinkedIn post text exceeds maximum length of 3000 characters (current: {len(content)})")

        if title and len(title) > 150:
            raise ValueError(f"LinkedIn post title exceeds maximum length of 150 characters (current: {len(title)})")

        if subtitle and len(subtitle) > 150:
            raise ValueError(f"LinkedIn post subtitle exceeds maximum length of 150 characters (current: {len(subtitle)})")

        # Prepare headers
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': self.api_version
        }

        # Determine if we're posting as a person or organization
        if self.organization_id:
            author = f"urn:li:organization:{self.organization_id}"
        elif hasattr(self, 'user_id_value') and self.user_id_value:
            author = f"urn:li:person:{self.user_id_value}"
        else:
            # If we don't have a user ID, try to get it from the user_info
            if self.user_info and isinstance(self.user_info, dict):
                if 'id' in self.user_info:
                    author = f"urn:li:person:{self.user_info['id']}"
                else:
                    # We don't have a valid user ID, raise an error
                    raise ValueError("LinkedIn user ID not found. Please authenticate first.")
            else:
                # We don't have valid user_info, raise an error
                raise ValueError("LinkedIn user info not found. Please authenticate first.")
        # Prepare post payload
        post_data = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        # Handle media attachments (image or URL)
        # if image_path:
        #     # Upload the image
        #     success, asset_or_error, _ = self._upload_image(image_path, image_description)
        #
        #     if not success:
        #         return {
        #             'platform': 'linkedin',
        #             'status': 'error',
        #             'error': asset_or_error
        #         }
        #
        #     # Add the image to the post
        #     post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
        #     post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
        #         "status": "READY",
        #         "description": {
        #             "text": image_description or content[:256]  # LinkedIn has a limit on description length
        #         },
        #         "media": asset_or_error,
        #         "title": {
        #             "text": title or content[:50]  # Use title or first 50 chars of content
        #         }
        #     }]
        # # Add URL if provided and no image
        # elif url:
        #     post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
        #     post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
        #         "status": "READY",
        #         "description": {
        #             "text": content[:256]  # LinkedIn has a limit on description length
        #         },
        #         "originalUrl": url,
        #         "title": {
        #             "text": title or content[:50]  # Use title or first 50 chars of content
        #         }
        #     }]

        try:
            # Create the post
            print("trying to post to linkedin")
            response = requests.post(
                f"{self.api_url}/ugcPosts",
                headers=headers,
                json=post_data
            )

            if response.status_code in (200, 201):
                post_id = response.headers.get('x-restli-id') or 'unknown'
                return {
                    'platform': 'linkedin',
                    'id': post_id,
                    'status': 'published'
                }
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"

                # Add specific guidance based on status code
                if response.status_code == 401:
                    error_msg += "\n\nThis is an authentication error. Your access token may be invalid or expired."
                    error_msg += "\n\n" + self.get_token_refresh_instructions()
                elif response.status_code == 403:
                    error_msg += "\n\nThis is a permissions error. Your access token doesn't have the necessary permissions."
                    error_msg += "\nEnsure your LinkedIn app has the following permissions: r_liteprofile, w_member_social"
                    error_msg += "\nIf posting as an organization, also ensure you have r_organization_social, w_organization_social permissions."
                elif response.status_code == 404:
                    error_msg += "\n\nResource not found. If posting as an organization, verify your organization ID is correct."
                elif response.status_code == 400:
                    error_msg += "\n\nBad request. This could be due to invalid data in your post."
                    error_msg += "\nCheck that your content follows LinkedIn's guidelines and doesn't exceed character limits."
                    if "media" in response.text:
                        error_msg += "\nThere may be an issue with the media (image or URL) you're trying to share."

                return {
                    'platform': 'linkedin',
                    'status': 'error',
                    'error': error_msg
                }
        except Exception as e:
            error_msg = str(e)

            # Add general troubleshooting guidance
            error_msg += "\n\nGeneral troubleshooting steps for LinkedIn API issues:"
            error_msg += "\n1. Verify your LinkedIn access token is valid and not expired"
            error_msg += "\n2. Check that your LinkedIn app has the necessary permissions"
            error_msg += "\n3. If posting with images, ensure the image file exists and is a supported format (JPG, PNG)"
            error_msg += "\n4. Check that your content doesn't exceed LinkedIn's character limits (3000 chars for post text)"
            error_msg += "\n5. If the error persists, generate a new access token"
            error_msg += "\n6. Ensure your network connection is stable"

            # If the error message contains authentication-related terms, add token refresh instructions
            if any(term in error_msg.lower() for term in ['auth', 'token', 'expired', 'invalid', 'unauthorized', '401']):
                error_msg += "\n\nYour access token may need to be refreshed. Here are the instructions:\n"
                error_msg += self.get_token_refresh_instructions()

            return {
                'platform': 'linkedin',
                'status': 'error',
                'error': error_msg
            }
