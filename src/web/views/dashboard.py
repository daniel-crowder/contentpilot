"""
Dashboard views for the web application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from ...database.setup import get_session, close_session
from ...database.models import Content, PublishingHistory, ContentAnalytics

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    """
    Dashboard index page.
    """
    session = get_session()
    
    try:
        # Get recent content
        recent_content = session.query(Content).order_by(Content.created_at.desc()).limit(5).all()
        
        # Get upcoming content
        today = datetime.now().date()
        upcoming_content = session.query(Content).filter(
            Content.publish_date >= today,
            Content.is_published == False,
            Content.is_draft == False
        ).order_by(Content.publish_date).limit(5).all()
        
        # Get recent publishing history
        recent_history = session.query(PublishingHistory).order_by(
            PublishingHistory.published_at.desc()
        ).limit(10).all()
        
        # Get content counts by platform
        platform_counts = {}
        for platform in ['twitter', 'linkedin', 'substack']:
            count = session.query(Content).filter(Content.platform == platform).count()
            platform_counts[platform] = count
        
        # Get content counts by status
        status_counts = {
            'draft': session.query(Content).filter(Content.is_draft == True).count(),
            'scheduled': session.query(Content).filter(
                Content.is_draft == False,
                Content.is_published == False
            ).count(),
            'published': session.query(Content).filter(Content.is_published == True).count()
        }
        
        # Get analytics summary
        analytics_summary = {
            'views': 0,
            'likes': 0,
            'shares': 0,
            'comments': 0
        }
        
        # Get analytics for the last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        analytics = session.query(ContentAnalytics).filter(
            ContentAnalytics.recorded_at >= thirty_days_ago
        ).all()
        
        for record in analytics:
            analytics_summary['views'] += record.views
            analytics_summary['likes'] += record.likes
            analytics_summary['shares'] += record.shares
            analytics_summary['comments'] += record.comments
        
        return render_template(
            'dashboard/index.html',
            recent_content=recent_content,
            upcoming_content=upcoming_content,
            recent_history=recent_history,
            platform_counts=platform_counts,
            status_counts=status_counts,
            analytics_summary=analytics_summary
        )
    
    finally:
        close_session(session)


@dashboard_bp.route('/calendar')
@login_required
def calendar():
    """
    Content calendar page.
    """
    session = get_session()
    
    try:
        # Get all content for calendar view
        all_content = session.query(Content).all()
        
        # Organize content by date
        calendar_data = {}
        
        for content in all_content:
            date_str = content.publish_date.strftime('%Y-%m-%d')
            
            if date_str not in calendar_data:
                calendar_data[date_str] = []
            
            calendar_data[date_str].append(content)
        
        return render_template('dashboard/calendar.html', calendar_data=calendar_data)
    
    finally:
        close_session(session)


@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """
    Analytics dashboard page.
    """
    session = get_session()
    
    try:
        # Get analytics data
        analytics_data = {
            'twitter': {
                'views': 0,
                'likes': 0,
                'shares': 0,
                'comments': 0
            },
            'linkedin': {
                'views': 0,
                'likes': 0,
                'shares': 0,
                'comments': 0
            },
            'substack': {
                'views': 0,
                'likes': 0,
                'shares': 0,
                'comments': 0
            }
        }
        
        # Get analytics for each platform
        for platform in ['twitter', 'linkedin', 'substack']:
            analytics = session.query(ContentAnalytics).filter(
                ContentAnalytics.platform == platform
            ).all()
            
            for record in analytics:
                analytics_data[platform]['views'] += record.views
                analytics_data[platform]['likes'] += record.likes
                analytics_data[platform]['shares'] += record.shares
                analytics_data[platform]['comments'] += record.comments
        
        return render_template('dashboard/analytics.html', analytics_data=analytics_data)
    
    finally:
        close_session(session)