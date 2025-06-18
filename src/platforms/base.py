"""
Base class for social media platforms.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Platform(ABC):
    """
    Abstract base class for all social media platforms.
    """
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the platform API.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def publish(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Publish content to the platform.
        
        Args:
            content: The content to publish
            **kwargs: Additional platform-specific parameters
            
        Returns:
            Dictionary with information about the published content
        """
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if the platform is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        pass