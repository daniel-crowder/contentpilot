"""
Database setup and configuration.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# Create the base class for declarative models
Base = declarative_base()

# Default to SQLite database if no DATABASE_URL is provided
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///social_media_publisher.db')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
session_factory = sessionmaker(bind=engine)

# Create thread-safe scoped session
Session = scoped_session(session_factory)

def init_db():
    """
    Initialize the database by creating all tables.
    """
    # Import all models to ensure they're registered with Base
    from .models import Content, PublishingHistory, User, Team, MediaAttachment
    
    # Create all tables
    Base.metadata.create_all(engine)

def get_session():
    """
    Get a database session.
    
    Returns:
        SQLAlchemy session
    """
    return Session()

def close_session(session):
    """
    Close a database session.
    
    Args:
        session: SQLAlchemy session to close
    """
    session.close()