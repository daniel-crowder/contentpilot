"""
Content management views for the web application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os
import pandas as pd
from werkzeug.utils import secure_filename

from ...database.setup import get_session, close_session
from ...database.models import Content, MediaAttachment, ContentTemplate
from ..auth import load_user
from ...platforms.twitter import TwitterPlatform
from ...platforms.linkedin import LinkedInPlatform
from ...platforms.substack import SubstackPlatform
from ...utils.scheduler import ContentScheduler
from ...data_sources.database_source import DatabaseDataSource

# Create blueprint
content_bp = Blueprint('content', __name__, url_prefix='/content')


@content_bp.route('/')
@login_required
def index():
    """
    Content list page.
    """
    session = get_session()

    try:
        # Get filter parameters
        platform = request.args.get('platform')
        status = request.args.get('status')

        # Start with a base query
        query = session.query(Content)

        # Apply filters
        if platform:
            query = query.filter(Content.platform == platform)

        if status == 'draft':
            query = query.filter(Content.is_draft == True)
        elif status == 'scheduled':
            query = query.filter(Content.is_draft == False, Content.is_published == False)
        elif status == 'published':
            query = query.filter(Content.is_published == True)

        # Get content
        contents = query.order_by(Content.publish_date.desc()).all()

        return render_template('content/index.html', contents=contents)

    finally:
        close_session(session)


@content_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create content page.
    """
    session = get_session()

    try:
        # Get templates for selection
        templates = session.query(ContentTemplate).all()

        # Handle form submission
        if request.method == 'POST':
            platform = request.form.get('platform')
            content = request.form.get('content')
            title = request.form.get('title')
            subtitle = request.form.get('subtitle')
            url = request.form.get('url')
            publish_date = request.form.get('publish_date')
            publish_time = request.form.get('publish_time', '09:00')
            is_draft = 'is_draft' in request.form

            # Validate form data
            if not platform or not content or not publish_date:
                flash('Platform, content, and publish date are required', 'error')
                return render_template('content/create.html', templates=templates)

            # Validate that title is provided for Substack
            if platform == 'substack' and not title:
                flash('Title is required for Substack content', 'error')
                return render_template('content/create.html', templates=templates)

            # Create new content
            try:
                publish_date_obj = datetime.strptime(publish_date, '%Y-%m-%d')

                new_content = Content(
                    platform=platform,
                    content=content,
                    title=title,
                    subtitle=subtitle,
                    url=url,
                    publish_date=publish_date_obj,
                    publish_time=publish_time,
                    is_draft=is_draft,
                    is_published=False,
                    author_id=current_user.id
                )

                session.add(new_content)
                session.commit()

                # Handle file uploads
                if 'media' in request.files:
                    media_files = request.files.getlist('media')

                    for media_file in media_files:
                        if media_file and media_file.filename:
                            filename = secure_filename(media_file.filename)
                            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                            media_file.save(file_path)

                            # Create media attachment
                            attachment = MediaAttachment(
                                content_id=new_content.id,
                                file_name=filename,
                                file_path=file_path,
                                file_type=media_file.content_type,
                                file_size=os.path.getsize(file_path)
                            )

                            session.add(attachment)

                    session.commit()

                flash('Content created successfully', 'success')
                return redirect(url_for('content.index'))

            except Exception as e:
                session.rollback()
                flash(f'Error creating content: {str(e)}', 'error')

        return render_template('content/create.html', templates=templates)

    finally:
        close_session(session)


@content_bp.route('/edit/<int:content_id>', methods=['GET', 'POST'])
@login_required
def edit(content_id):
    """
    Edit content page.
    """
    session = get_session()

    try:
        # Get content
        content = session.query(Content).filter(Content.id == content_id).first()

        if not content:
            flash('Content not found', 'error')
            return redirect(url_for('content.index'))

        # Get media attachments
        attachments = session.query(MediaAttachment).filter(
            MediaAttachment.content_id == content_id
        ).all()

        # Handle form submission
        if request.method == 'POST':
            content.platform = request.form.get('platform')
            content.content = request.form.get('content')
            content.title = request.form.get('title')
            content.subtitle = request.form.get('subtitle')
            content.url = request.form.get('url')

            publish_date = request.form.get('publish_date')
            if publish_date:
                content.publish_date = datetime.strptime(publish_date, '%Y-%m-%d')

            content.publish_time = request.form.get('publish_time', '09:00')
            content.is_draft = 'is_draft' in request.form

            # Validate that title is provided for Substack
            if content.platform == 'substack' and not content.title:
                flash('Title is required for Substack content', 'error')
                return render_template('content/edit.html', content=content, attachments=attachments)

            try:
                # Handle file uploads
                if 'media' in request.files:
                    media_files = request.files.getlist('media')

                    for media_file in media_files:
                        if media_file and media_file.filename:
                            filename = secure_filename(media_file.filename)
                            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                            media_file.save(file_path)

                            # Create media attachment
                            attachment = MediaAttachment(
                                content_id=content.id,
                                file_name=filename,
                                file_path=file_path,
                                file_type=media_file.content_type,
                                file_size=os.path.getsize(file_path)
                            )

                            session.add(attachment)

                # Handle attachment deletions
                for attachment_id in request.form.getlist('delete_attachment'):
                    attachment = session.query(MediaAttachment).filter(
                        MediaAttachment.id == int(attachment_id)
                    ).first()

                    if attachment:
                        # Delete file
                        if os.path.exists(attachment.file_path):
                            os.remove(attachment.file_path)

                        # Delete record
                        session.delete(attachment)

                session.commit()
                flash('Content updated successfully', 'success')
                return redirect(url_for('content.index'))

            except Exception as e:
                session.rollback()
                flash(f'Error updating content: {str(e)}', 'error')

        return render_template('content/edit.html', content=content, attachments=attachments)

    finally:
        close_session(session)


@content_bp.route('/publish/<int:content_id>', methods=['POST'])
@login_required
def publish(content_id):
    """
    Publish content immediately, even if it's a draft.
    """
    session = get_session()

    try:
        # Get content
        content = session.query(Content).filter(Content.id == content_id).first()

        if not content:
            flash('Content not found', 'error')
            return redirect(url_for('content.index'))

        # Update content with form data
        content.platform = request.form.get('platform')
        content.content = request.form.get('content')
        content.title = request.form.get('title')
        content.subtitle = request.form.get('subtitle')
        content.url = request.form.get('url')

        publish_date = request.form.get('publish_date')
        if publish_date:
            content.publish_date = datetime.strptime(publish_date, '%Y-%m-%d')

        content.publish_time = request.form.get('publish_time', '09:00')
        content.is_draft = 'is_draft' in request.form

        # Validate that title is provided for Substack
        if content.platform == 'substack' and not content.title:
            flash('Title is required for Substack content', 'error')
            return redirect(url_for('content.edit', content_id=content_id))

        # Save changes
        session.commit()

        # Import necessary modules
        from ...platforms.twitter import TwitterPlatform
        from ...platforms.linkedin import LinkedInPlatform
        from ...platforms.substack import SubstackPlatform
        from ...utils.scheduler import ContentScheduler
        from ...data_sources.database_source import DatabaseDataSource

        # Set up platforms
        platforms = {}

        if content.platform == 'twitter':
            platforms['twitter'] = TwitterPlatform()
        elif content.platform == 'linkedin':
            platforms['linkedin'] = LinkedInPlatform(user_id=current_user.id)
        elif content.platform == 'substack':
            platforms['substack'] = SubstackPlatform()

        # Set up data source
        data_source = DatabaseDataSource()

        # Set up scheduler
        scheduler = ContentScheduler(data_source, platforms)

        # Create a DataFrame with just this content
        content_dict = data_source._content_to_dict(content)
        df = pd.DataFrame([content_dict])

        # Publish content
        try:
            result = scheduler._publish_content(df.iloc[0])

            if result.get('status') == 'error':
                flash(f"Error publishing to {result.get('platform')}: {result.get('error')}", 'error')
            else:
                # Mark as published in the database
                data_source.mark_as_published(
                    content_id=content.id,
                    platform_post_id=result.get('id'),
                    platform_post_url=result.get('url'),
                    status='success'
                )
                flash(f"Successfully published to {result.get('platform')}", 'success')

            return redirect(url_for('content.index'))

        except Exception as e:
            flash(f'Error publishing content: {str(e)}', 'error')
            return redirect(url_for('content.edit', content_id=content_id))

    except Exception as e:
        session.rollback()
        flash(f'Error updating content: {str(e)}', 'error')
        return redirect(url_for('content.edit', content_id=content_id))

    finally:
        close_session(session)


@content_bp.route('/delete/<int:content_id>', methods=['POST'])
@login_required
def delete(content_id):
    """
    Delete content.
    """
    session = get_session()

    try:
        # Get content
        content = session.query(Content).filter(Content.id == content_id).first()

        if not content:
            flash('Content not found', 'error')
            return redirect(url_for('content.index'))

        # Delete media attachments
        attachments = session.query(MediaAttachment).filter(
            MediaAttachment.content_id == content_id
        ).all()

        for attachment in attachments:
            # Delete file
            if os.path.exists(attachment.file_path):
                os.remove(attachment.file_path)

            # Delete record
            session.delete(attachment)

        # Delete content
        session.delete(content)
        session.commit()

        flash('Content deleted successfully', 'success')
        return redirect(url_for('content.index'))

    except Exception as e:
        session.rollback()
        flash(f'Error deleting content: {str(e)}', 'error')
        return redirect(url_for('content.index'))

    finally:
        close_session(session)


@content_bp.route('/create-and-publish', methods=['POST'])
@login_required
def create_and_publish():
    """
    Create content and publish it immediately.
    """
    session = get_session()

    try:
        # Get form data
        platform = request.form.get('platform')
        content_text = request.form.get('content')
        title = request.form.get('title')
        subtitle = request.form.get('subtitle')
        url = request.form.get('url')
        publish_date = request.form.get('publish_date')
        publish_time = request.form.get('publish_time', '09:00')
        is_draft = 'is_draft' in request.form

        # Validate form data
        if not platform or not content_text or not publish_date:
            flash('Platform, content, and publish date are required', 'error')
            return redirect(url_for('content.create'))

        # Validate that title is provided for Substack
        if platform == 'substack' and not title:
            flash('Title is required for Substack content', 'error')
            return redirect(url_for('content.create'))

        # Create new content
        try:
            publish_date_obj = datetime.strptime(publish_date, '%Y-%m-%d')

            new_content = Content(
                platform=platform,
                content=content_text,
                title=title,
                subtitle=subtitle,
                url=url,
                publish_date=publish_date_obj,
                publish_time=publish_time,
                is_draft=is_draft,
                is_published=False,
                author_id=current_user.id
            )

            session.add(new_content)
            session.commit()

            # Handle file uploads
            if 'media' in request.files:
                media_files = request.files.getlist('media')

                for media_file in media_files:
                    if media_file and media_file.filename:
                        filename = secure_filename(media_file.filename)
                        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        media_file.save(file_path)

                        # Create media attachment
                        attachment = MediaAttachment(
                            content_id=new_content.id,
                            file_name=filename,
                            file_path=file_path,
                            file_type=media_file.content_type,
                            file_size=os.path.getsize(file_path)
                        )

                        session.add(attachment)

                session.commit()

            # Now publish the content
            # Import necessary modules
            from ...platforms.twitter import TwitterPlatform
            from ...platforms.linkedin import LinkedInPlatform
            from ...platforms.substack import SubstackPlatform
            from ...utils.scheduler import ContentScheduler
            from ...data_sources.database_source import DatabaseDataSource

            # Set up platforms
            platforms = {}

            if platform == 'twitter':
                platforms['twitter'] = TwitterPlatform()
            elif platform == 'linkedin':
                platforms['linkedin'] = LinkedInPlatform(user_id=current_user.id)
            elif platform == 'substack':
                platforms['substack'] = SubstackPlatform()

            # Set up data source
            data_source = DatabaseDataSource()

            # Set up scheduler
            scheduler = ContentScheduler(data_source, platforms)

            # Create a DataFrame with just this content
            content_dict = data_source._content_to_dict(new_content)
            df = pd.DataFrame([content_dict])

            # Publish content
            try:
                result = scheduler._publish_content(df.iloc[0])

                if result.get('status') == 'error':
                    flash(f"Error publishing to {result.get('platform')}: {result.get('error')}", 'error')
                else:
                    # Mark as published in the database
                    data_source.mark_as_published(
                        content_id=new_content.id,
                        platform_post_id=result.get('id'),
                        platform_post_url=result.get('url'),
                        status='success'
                    )
                    flash(f"Content created and published to {result.get('platform')}", 'success')

                return redirect(url_for('content.index'))

            except Exception as e:
                flash(f'Error publishing content: {str(e)}', 'error')
                return redirect(url_for('content.edit', content_id=new_content.id))

        except Exception as e:
            session.rollback()
            flash(f'Error creating content: {str(e)}', 'error')
            return redirect(url_for('content.create'))

    except Exception as e:
        session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('content.create'))

    finally:
        close_session(session)


@content_bp.route('/templates')
@login_required
def templates():
    """
    Content templates page.
    """
    session = get_session()

    try:
        # Get templates
        templates = session.query(ContentTemplate).all()

        return render_template('content/templates.html', templates=templates)

    finally:
        close_session(session)


@content_bp.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """
    Create content template page.
    """
    session = get_session()

    try:
        # Handle form submission
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            platform = request.form.get('platform')
            template_content = request.form.get('template_content')

            # Validate form data
            if not name or not platform or not template_content:
                flash('Name, platform, and template content are required', 'error')
                return render_template('content/create_template.html')

            # Create new template
            try:
                new_template = ContentTemplate(
                    name=name,
                    description=description,
                    platform=platform,
                    template_content=template_content,
                    author_id=current_user.id
                )

                session.add(new_template)
                session.commit()

                flash('Template created successfully', 'success')
                return redirect(url_for('content.templates'))

            except Exception as e:
                session.rollback()
                flash(f'Error creating template: {str(e)}', 'error')

        return render_template('content/create_template.html')

    finally:
        close_session(session)


@content_bp.route('/templates/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """
    Edit content template page.
    """
    session = get_session()

    try:
        # Get template
        template = session.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()

        if not template:
            flash('Template not found', 'error')
            return redirect(url_for('content.templates'))

        # Handle form submission
        if request.method == 'POST':
            template.name = request.form.get('name')
            template.description = request.form.get('description')
            template.platform = request.form.get('platform')
            template.template_content = request.form.get('template_content')

            # Validate form data
            if not template.name or not template.platform or not template.template_content:
                flash('Name, platform, and template content are required', 'error')
                return render_template('content/edit_template.html', template=template)

            try:
                session.commit()
                flash('Template updated successfully', 'success')
                return redirect(url_for('content.templates'))

            except Exception as e:
                session.rollback()
                flash(f'Error updating template: {str(e)}', 'error')

        return render_template('content/edit_template.html', template=template)

    finally:
        close_session(session)


@content_bp.route('/templates/delete/<int:template_id>', methods=['POST'])
@login_required
def delete_template(template_id):
    """
    Delete content template.
    """
    session = get_session()

    try:
        # Get template
        template = session.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()

        if not template:
            flash('Template not found', 'error')
            return redirect(url_for('content.templates'))

        # Delete template
        session.delete(template)
        session.commit()

        flash('Template deleted successfully', 'success')
        return redirect(url_for('content.templates'))

    except Exception as e:
        session.rollback()
        flash(f'Error deleting template: {str(e)}', 'error')
        return redirect(url_for('content.templates'))

    finally:
        close_session(session)


@content_bp.route('/templates/get/<int:template_id>')
@login_required
def get_template(template_id):
    """
    Get content template as JSON.
    """
    session = get_session()

    try:
        # Get template
        template = session.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()

        if not template:
            return jsonify({'error': 'Template not found'}), 404

        return jsonify({
            'id': template.id,
            'name': template.name,
            'platform': template.platform,
            'template_content': template.template_content
        })

    finally:
        close_session(session)


@content_bp.route('/bulk_action/<action>', methods=['POST'])
@login_required
def bulk_action(action):
    """
    Handle bulk actions on content items.

    Args:
        action: The action to perform (publish, mark_as_draft, mark_as_scheduled, delete)
    """
    content_ids = request.form.getlist('content_ids')

    if not content_ids:
        flash('No content items selected', 'error')
        return redirect(url_for('content.index'))

    session = get_session()

    try:
        # Get the selected content items
        contents = session.query(Content).filter(Content.id.in_(content_ids)).all()

        if not contents:
            flash('No content items found', 'error')
            return redirect(url_for('content.index'))

        if action == 'delete':
            # Delete content items
            deleted_count = 0
            for content in contents:
                # Delete media attachments
                attachments = session.query(MediaAttachment).filter(
                    MediaAttachment.content_id == content.id
                ).all()

                for attachment in attachments:
                    # Delete file
                    if os.path.exists(attachment.file_path):
                        os.remove(attachment.file_path)

                    # Delete record
                    session.delete(attachment)

                # Delete content
                session.delete(content)
                deleted_count += 1

            session.commit()
            flash(f'Successfully deleted {deleted_count} content items', 'success')

        elif action == 'mark_as_draft':
            # Mark content items as drafts
            updated_count = 0
            for content in contents:
                content.is_draft = True
                updated_count += 1

            session.commit()
            flash(f'Successfully marked {updated_count} content items as drafts', 'success')

        elif action == 'mark_as_scheduled':
            # Mark content items as scheduled (not draft)
            updated_count = 0
            for content in contents:
                content.is_draft = False
                updated_count += 1

            session.commit()
            flash(f'Successfully marked {updated_count} content items as scheduled', 'success')

        elif action == 'publish':
            # Publish content items
            published_count = 0
            error_count = 0

            # Set up data source
            data_source = DatabaseDataSource()

            for content in contents:
                # Skip already published content
                if content.is_published:
                    continue

                # Set up platforms
                platforms = {}

                if content.platform == 'twitter':
                    platforms['twitter'] = TwitterPlatform()
                elif content.platform == 'linkedin':
                    platforms['linkedin'] = LinkedInPlatform(user_id=current_user.id)
                elif content.platform == 'substack':
                    platforms['substack'] = SubstackPlatform()
                else:
                    error_count += 1
                    continue

                # Set up scheduler
                scheduler = ContentScheduler(data_source, platforms)

                # Create a DataFrame with just this content
                content_dict = data_source._content_to_dict(content)
                df = pd.DataFrame([content_dict])

                try:
                    # Publish content
                    result = scheduler._publish_content(df.iloc[0])

                    if result.get('status') == 'error':
                        error_count += 1
                    else:
                        # Mark as published in the database
                        data_source.mark_as_published(
                            content_id=content.id,
                            platform_post_id=result.get('id'),
                            platform_post_url=result.get('url'),
                            status='success'
                        )
                        published_count += 1

                except Exception as e:
                    error_count += 1

            if published_count > 0:
                flash(f'Successfully published {published_count} content items', 'success')

            if error_count > 0:
                flash(f'Failed to publish {error_count} content items', 'error')

        else:
            flash(f'Unknown action: {action}', 'error')

        return redirect(url_for('content.index'))

    except Exception as e:
        session.rollback()
        flash(f'Error performing bulk action: {str(e)}', 'error')
        return redirect(url_for('content.index'))

    finally:
        close_session(session)
