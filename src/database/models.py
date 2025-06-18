"""
Database models for the Social Media Content Publisher.
"""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from .setup import Base

# Association table for team members
team_members = Table(
    'team_members',
    Base.metadata,
    Column('team_id', Integer, ForeignKey('teams.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True)
)

class User(Base):
    """
    User model for authentication and authorization.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    contents = relationship("Content", back_populates="author")
    teams = relationship("Team", secondary=team_members, back_populates="members")

    def __repr__(self):
        return f"<User {self.username}>"

class Team(Base):
    """
    Team model for grouping users.
    """
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    members = relationship("User", secondary=team_members, back_populates="teams")
    contents = relationship("Content", back_populates="team")

    def __repr__(self):
        return f"<Team {self.name}>"

class Content(Base):
    """
    Content model for storing social media posts.
    """
    __tablename__ = 'contents'

    id = Column(Integer, primary_key=True)
    platform = Column(String(50), nullable=False)  # twitter, linkedin, substack
    content = Column(Text, nullable=False)
    title = Column(String(255))  # Required for Substack
    subtitle = Column(String(255))  # Optional for Substack
    url = Column(String(255))  # Optional for LinkedIn
    publish_date = Column(DateTime, nullable=False)
    publish_time = Column(String(5), default="09:00")  # Format: HH:MM
    is_published = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Foreign keys
    author_id = Column(Integer, ForeignKey('users.id'))
    team_id = Column(Integer, ForeignKey('teams.id'))

    # Relationships
    author = relationship("User", back_populates="contents")
    team = relationship("Team", back_populates="contents")
    media_attachments = relationship("MediaAttachment", back_populates="content")
    publishing_history = relationship("PublishingHistory", back_populates="content")

    def __repr__(self):
        return f"<Content {self.id} for {self.platform}>"

    def to_dict(self):
        """
        Convert the content to a dictionary.

        Returns:
            Dictionary representation of the content
        """
        return {
            'id': self.id,
            'platform': self.platform,
            'content': self.content,
            'title': self.title,
            'subtitle': self.subtitle,
            'url': self.url,
            'publish_date': self.publish_date.strftime('%Y-%m-%d'),
            'publish_time': self.publish_time,
            'is_published': self.is_published,
            'is_draft': self.is_draft,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'author_id': self.author_id,
            'team_id': self.team_id
        }

class PublishingHistory(Base):
    """
    Publishing history model for tracking content publishing.
    """
    __tablename__ = 'publishing_history'

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey('contents.id'), nullable=False)
    platform = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # success, error
    platform_post_id = Column(String(255))  # ID of the post on the platform
    platform_post_url = Column(String(255))  # URL of the post on the platform
    error_message = Column(Text)
    published_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    content = relationship("Content", back_populates="publishing_history")

    def __repr__(self):
        return f"<PublishingHistory {self.id} for content {self.content_id}>"

class MediaAttachment(Base):
    """
    Media attachment model for storing images and other media.
    """
    __tablename__ = 'media_attachments'

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey('contents.id'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(50))  # image, video, etc.
    file_size = Column(Integer)  # Size in bytes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    content = relationship("Content", back_populates="media_attachments")

    def __repr__(self):
        return f"<MediaAttachment {self.id} for content {self.content_id}>"

class ContentTemplate(Base):
    """
    Content template model for storing reusable content templates.
    """
    __tablename__ = 'content_templates'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    platform = Column(String(50), nullable=False)
    template_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Foreign keys
    author_id = Column(Integer, ForeignKey('users.id'))
    team_id = Column(Integer, ForeignKey('teams.id'))

    def __repr__(self):
        return f"<ContentTemplate {self.name}>"

class ContentAnalytics(Base):
    """
    Content analytics model for tracking engagement metrics.
    """
    __tablename__ = 'content_analytics'

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey('contents.id'), nullable=False)
    platform = Column(String(50), nullable=False)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<ContentAnalytics {self.id} for content {self.content_id}>"

class PlatformCredential(Base):
    """
    Platform credential model for storing OAuth tokens and other credentials.
    """
    __tablename__ = 'platform_credentials'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    platform = Column(String(50), nullable=False)  # twitter, linkedin, substack
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_type = Column(String(50))
    expires_at = Column(DateTime)
    scope = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", backref="platform_credentials")

    def __repr__(self):
        return f"<PlatformCredential {self.id} for user {self.user_id} on {self.platform}>"

    def is_expired(self):
        """
        Check if the access token is expired.

        Returns:
            True if the token is expired, False otherwise
        """
        if not self.expires_at:
            return False

        return datetime.datetime.utcnow() > self.expires_at
