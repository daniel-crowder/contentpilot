"""
Authentication utilities for the web application.
"""
import hashlib
from flask_login import UserMixin
from typing import Optional

from ..database.setup import get_session, close_session
from ..database.models import User


class UserLogin(UserMixin):
    """
    User class for Flask-Login.
    """
    
    def __init__(self, user_id: int, username: str, email: str, is_admin: bool = False):
        self.id = user_id
        self.username = username
        self.email = email
        self.is_admin = is_admin
    
    def get_id(self):
        return str(self.id)


def load_user(user_id: str) -> Optional[UserLogin]:
    """
    Load a user from the database.
    
    Args:
        user_id: User ID
        
    Returns:
        UserLogin object or None if user not found
    """
    session = get_session()
    
    try:
        user = session.query(User).filter(User.id == int(user_id)).first()
        
        if user:
            return UserLogin(
                user_id=user.id,
                username=user.username,
                email=user.email,
                is_admin=user.is_admin
            )
        
        return None
    
    finally:
        close_session(session)


def authenticate_user(username: str, password: str) -> Optional[UserLogin]:
    """
    Authenticate a user.
    
    Args:
        username: Username
        password: Password
        
    Returns:
        UserLogin object or None if authentication failed
    """
    session = get_session()
    
    try:
        # Find user by username
        user = session.query(User).filter(User.username == username).first()
        
        if not user:
            return None
        
        # Check password
        password_hash = hash_password(password)
        
        if user.password_hash != password_hash:
            return None
        
        return UserLogin(
            user_id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin
        )
    
    finally:
        close_session(session)


def hash_password(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Password to hash
        
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username: str, email: str, password: str, first_name: str = None, last_name: str = None, is_admin: bool = False) -> Optional[int]:
    """
    Create a new user.
    
    Args:
        username: Username
        email: Email
        password: Password
        first_name: First name
        last_name: Last name
        is_admin: Whether the user is an admin
        
    Returns:
        User ID or None if creation failed
    """
    session = get_session()
    
    try:
        # Check if username or email already exists
        existing_user = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            return None
        
        # Create new user
        password_hash = hash_password(password)
        
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin
        )
        
        session.add(new_user)
        session.commit()
        
        return new_user.id
    
    except Exception as e:
        session.rollback()
        print(f"Error creating user: {str(e)}")
        return None
    
    finally:
        close_session(session)