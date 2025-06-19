"""
Analytics views for the web application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json

from ...database.setup import get_session, close_session
from ...database.models import Content, PublishingHistory, ContentAnalytics

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/')
@login_required
def index():
    """
    Analytics dashboard page.
    """
    session = get_session()

    try:
        # Get filter parameters
        platform = request.args.get('platform')
        period = request.args.get('period', '30')  # Default to 30 days

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(period))

        # Get analytics data
        query = session.query(ContentAnalytics)

        if platform:
            query = query.filter(ContentAnalytics.platform == platform)

        query = query.filter(ContentAnalytics.recorded_at >= start_date)
        analytics = query.all()

        # Prepare data for charts
        chart_data = {
            'labels': [],
            'views': [],
            'likes': [],
            'shares': [],
            'comments': []
        }

        # Group by date
        date_data = {}
        for record in analytics:
            date_str = record.recorded_at.strftime('%Y-%m-%d')

            if date_str not in date_data:
                date_data[date_str] = {
                    'views': 0,
                    'likes': 0,
                    'shares': 0,
                    'comments': 0
                }

            date_data[date_str]['views'] += record.views
            date_data[date_str]['likes'] += record.likes
            date_data[date_str]['shares'] += record.shares
            date_data[date_str]['comments'] += record.comments

        # Sort dates and prepare chart data
        sorted_dates = sorted(date_data.keys())

        for date_str in sorted_dates:
            chart_data['labels'].append(date_str)
            chart_data['views'].append(date_data[date_str]['views'])
            chart_data['likes'].append(date_data[date_str]['likes'])
            chart_data['shares'].append(date_data[date_str]['shares'])
            chart_data['comments'].append(date_data[date_str]['comments'])

        # Get platform-specific data
        platform_data = {}
        for platform_name in ['twitter', 'linkedin', 'substack', 'wordpress']:
            platform_records = session.query(ContentAnalytics).filter(
                ContentAnalytics.platform == platform_name,
                ContentAnalytics.recorded_at >= start_date
            ).all()

            platform_data[platform_name] = {
                'views': sum(record.views for record in platform_records),
                'likes': sum(record.likes for record in platform_records),
                'shares': sum(record.shares for record in platform_records),
                'comments': sum(record.comments for record in platform_records)
            }

        # Get top performing content
        top_content = session.query(
            Content,
            ContentAnalytics.views,
            ContentAnalytics.likes,
            ContentAnalytics.shares,
            ContentAnalytics.comments
        ).join(
            ContentAnalytics,
            Content.id == ContentAnalytics.content_id
        ).filter(
            ContentAnalytics.recorded_at >= start_date
        ).order_by(
            ContentAnalytics.views.desc()
        ).limit(5).all()

        return render_template(
            'analytics/index.html',
            chart_data=json.dumps(chart_data),
            platform_data=platform_data,
            top_content=top_content,
            selected_platform=platform,
            selected_period=period
        )

    finally:
        close_session(session)


@analytics_bp.route('/content/<int:content_id>')
@login_required
def content_analytics(content_id):
    """
    Analytics for a specific content.
    """
    session = get_session()

    try:
        # Get content
        content = session.query(Content).filter(Content.id == content_id).first()

        if not content:
            flash('Content not found', 'error')
            return redirect(url_for('analytics.index'))

        # Get analytics data
        analytics = session.query(ContentAnalytics).filter(
            ContentAnalytics.content_id == content_id
        ).order_by(
            ContentAnalytics.recorded_at
        ).all()

        # Prepare data for charts
        chart_data = {
            'labels': [],
            'views': [],
            'likes': [],
            'shares': [],
            'comments': []
        }

        for record in analytics:
            date_str = record.recorded_at.strftime('%Y-%m-%d')
            chart_data['labels'].append(date_str)
            chart_data['views'].append(record.views)
            chart_data['likes'].append(record.likes)
            chart_data['shares'].append(record.shares)
            chart_data['comments'].append(record.comments)

        return render_template(
            'analytics/content.html',
            content=content,
            chart_data=json.dumps(chart_data),
            analytics=analytics
        )

    finally:
        close_session(session)


@analytics_bp.route('/update/<int:content_id>', methods=['GET', 'POST'])
@login_required
def update_analytics(content_id):
    """
    Update analytics for a specific content.
    """
    session = get_session()

    try:
        # Get content
        content = session.query(Content).filter(Content.id == content_id).first()

        if not content:
            flash('Content not found', 'error')
            return redirect(url_for('analytics.index'))

        # Handle form submission
        if request.method == 'POST':
            views = int(request.form.get('views', 0))
            likes = int(request.form.get('likes', 0))
            shares = int(request.form.get('shares', 0))
            comments = int(request.form.get('comments', 0))

            # Create new analytics record
            try:
                new_record = ContentAnalytics(
                    content_id=content_id,
                    platform=content.platform,
                    views=views,
                    likes=likes,
                    shares=shares,
                    comments=comments,
                    recorded_at=datetime.now()
                )

                session.add(new_record)
                session.commit()

                flash('Analytics updated successfully', 'success')
                return redirect(url_for('analytics.content_analytics', content_id=content_id))

            except Exception as e:
                session.rollback()
                flash(f'Error updating analytics: {str(e)}', 'error')

        return render_template('analytics/update.html', content=content)

    finally:
        close_session(session)


@analytics_bp.route('/export')
@login_required
def export_analytics():
    """
    Export analytics data as JSON.
    """
    session = get_session()

    try:
        # Get filter parameters
        platform = request.args.get('platform')
        period = request.args.get('period', '30')  # Default to 30 days

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(period))

        # Get analytics data
        query = session.query(ContentAnalytics)

        if platform:
            query = query.filter(ContentAnalytics.platform == platform)

        query = query.filter(ContentAnalytics.recorded_at >= start_date)
        analytics = query.all()

        # Prepare export data
        export_data = []

        for record in analytics:
            content = session.query(Content).filter(Content.id == record.content_id).first()

            if content:
                export_data.append({
                    'content_id': record.content_id,
                    'platform': record.platform,
                    'content': content.content[:100] + '...' if len(content.content) > 100 else content.content,
                    'publish_date': content.publish_date.strftime('%Y-%m-%d'),
                    'views': record.views,
                    'likes': record.likes,
                    'shares': record.shares,
                    'comments': record.comments,
                    'recorded_at': record.recorded_at.strftime('%Y-%m-%d %H:%M:%S')
                })

        return jsonify(export_data)

    finally:
        close_session(session)
