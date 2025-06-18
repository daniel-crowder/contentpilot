"""
Substack platform implementation.
"""
import os
import json
import requests
from typing import Dict, Any, Optional

from .base import Platform


class SubstackPlatform(Platform):
    """
    Platform implementation for Substack.
    
    Note: Substack doesn't have an official API, so this implementation uses
    a combination of authentication cookies and web requests to simulate
    publishing through the web interface.
    """
    
    def __init__(
        self,
        publication_name: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        cookie: Optional[str] = None
    ):
        """
        Initialize the Substack platform.
        
        Args:
            publication_name: Name of your Substack publication (e.g., 'yourpublication' for yourpublication.substack.com)
            email: Substack login email
            password: Substack login password
            cookie: Alternatively, provide a session cookie directly
            
        If any of the parameters are None, they will be read from environment variables:
        - SUBSTACK_PUBLICATION_NAME
        - SUBSTACK_EMAIL
        - SUBSTACK_PASSWORD
        - SUBSTACK_COOKIE
        
        Note: Either (email and password) or cookie must be provided
        """
        self.publication_name = publication_name or os.environ.get('SUBSTACK_PUBLICATION_NAME')
        self.email = email or os.environ.get('SUBSTACK_EMAIL')
        self.password = password or os.environ.get('SUBSTACK_PASSWORD')
        self.cookie = cookie or os.environ.get('SUBSTACK_COOKIE')
        
        self.session = requests.Session()
        self.authenticated = False
        
        # Validate credentials
        if not self.publication_name:
            raise ValueError("Substack publication name is missing")
        
        if not (self.cookie or (self.email and self.password)):
            raise ValueError("Substack credentials are missing. Provide either cookie or email and password.")
        
        # Set base URL
        self.base_url = f"https://{self.publication_name}.substack.com"
        self.api_url = f"{self.base_url}/api/v1"
    
    def authenticate(self) -> bool:
        """
        Authenticate with Substack.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        # If we already have a cookie, use it
        if self.cookie:
            self.session.cookies.set('substack.sid', self.cookie)
            try:
                # Test if the cookie works by fetching user info
                response = self.session.get(f"{self.api_url}/user/me")
                if response.status_code == 200:
                    self.authenticated = True
                    return True
            except Exception as e:
                print(f"Substack authentication with cookie failed: {str(e)}")
        
        # Otherwise, try to log in with email and password
        if self.email and self.password:
            try:
                # First, get the CSRF token
                response = self.session.get(f"{self.base_url}/sign-in")
                
                # Now log in
                login_data = {
                    "email": self.email,
                    "password": self.password,
                    "redirect": "/",
                    "for_pub": self.publication_name
                }
                
                response = self.session.post(
                    f"{self.base_url}/api/v1/login",
                    json=login_data
                )
                
                if response.status_code == 200:
                    # Store the cookie for future use
                    self.cookie = self.session.cookies.get('substack.sid')
                    self.authenticated = True
                    return True
                else:
                    print(f"Substack login failed: {response.text}")
                    return False
            except Exception as e:
                print(f"Substack authentication failed: {str(e)}")
                return False
        
        return False
    
    def is_authenticated(self) -> bool:
        """
        Check if the platform is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        return self.authenticated
    
    def publish(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Publish a post to Substack.
        
        Args:
            content: The post content (HTML supported)
            **kwargs: Additional parameters:
                - title: Post title (required)
                - subtitle: Optional post subtitle
                - is_draft: Whether to save as draft (default: False)
                
        Returns:
            Dictionary with information about the published post
            
        Raises:
            ValueError: If not authenticated or if required parameters are missing
        """
        if not self.is_authenticated() and not self.authenticate():
            raise ValueError("Not authenticated with Substack")
        
        # Get required parameters
        title = kwargs.get('title')
        if not title:
            raise ValueError("Title is required for Substack posts")
        
        # Get optional parameters
        subtitle = kwargs.get('subtitle', '')
        is_draft = kwargs.get('is_draft', False)
        
        # Prepare post data
        post_data = {
            "title": title,
            "subtitle": subtitle,
            "body": content,
            "audience": "everyone" if not is_draft else "only_me",
            "post_type": "newsletter",
            "publication_id": self.publication_name
        }
        
        try:
            # Create the post
            response = self.session.post(
                f"{self.api_url}/posts",
                json=post_data
            )
            
            if response.status_code in (200, 201):
                post_data = response.json()
                post_id = post_data.get('id', 'unknown')
                post_slug = post_data.get('slug', 'unknown')
                
                return {
                    'platform': 'substack',
                    'id': post_id,
                    'url': f"{self.base_url}/p/{post_slug}",
                    'status': 'draft' if is_draft else 'published'
                }
            else:
                return {
                    'platform': 'substack',
                    'status': 'error',
                    'error': f"API error: {response.status_code} - {response.text}"
                }
        except Exception as e:
            return {
                'platform': 'substack',
                'status': 'error',
                'error': str(e)
            }