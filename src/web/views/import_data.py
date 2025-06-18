"""
Data import views for the web application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, session
from flask_login import login_required, current_user
import pandas as pd
import os
from werkzeug.utils import secure_filename

from ...database.setup import get_session, close_session
from ...database.models import Content
from ...data_sources.csv_source import CSVDataSource
from ...data_sources.google_sheets_source import GoogleSheetsDataSource
from ...data_sources.database_source import DatabaseDataSource

# Create blueprint
import_bp = Blueprint('import', __name__, url_prefix='/import')


@import_bp.route('/')
@login_required
def index():
    """
    Data import landing page.
    """
    return render_template('import/index.html')


@import_bp.route('/csv', methods=['GET', 'POST'])
@login_required
def csv_import():
    """
    CSV import page.
    """
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'csv_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['csv_file']

        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            try:
                # Try to read the file as CSV
                csv_source = CSVDataSource(file_path)
                df = csv_source.get_content()

                # Store the file path in session for later use
                session['csv_file_path'] = file_path

                # Redirect to preview page
                return redirect(url_for('import.preview', source_type='csv'))

            except Exception as e:
                flash(f'Error reading CSV file: {str(e)}', 'error')
                # Delete the file if there was an error
                if os.path.exists(file_path):
                    os.remove(file_path)

    return render_template('import/csv.html')


@import_bp.route('/google-sheets', methods=['GET', 'POST'])
@login_required
def google_sheets_import():
    """
    Google Sheets import page.
    """
    if request.method == 'POST':
        sheet_id = request.form.get('sheet_id')
        range_name = request.form.get('range_name', 'A1:Z1000')

        if not sheet_id:
            flash('Sheet ID is required', 'error')
            return redirect(request.url)

        try:
            # Try to connect to the Google Sheet
            sheets_source = GoogleSheetsDataSource(sheet_id, range_name)
            df = sheets_source.get_content()

            # Store the sheet info in session for later use
            session['sheet_id'] = sheet_id
            session['range_name'] = range_name

            # Redirect to preview page
            return redirect(url_for('import.preview', source_type='google_sheets'))

        except Exception as e:
            flash(f'Error connecting to Google Sheet: {str(e)}', 'error')

    return render_template('import/google_sheets.html')


@import_bp.route('/preview/<source_type>')
@login_required
def preview(source_type):
    """
    Preview data before import.

    Args:
        source_type: Type of data source ('csv' or 'google_sheets')
    """
    try:
        df = None

        if source_type == 'csv':
            file_path = session.get('csv_file_path')
            if not file_path or not os.path.exists(file_path):
                flash('CSV file not found', 'error')
                return redirect(url_for('import.csv_import'))

            csv_source = CSVDataSource(file_path)
            df = csv_source.get_content()

        elif source_type == 'google_sheets':
            sheet_id = session.get('sheet_id')
            range_name = session.get('range_name')

            if not sheet_id:
                flash('Google Sheet information not found', 'error')
                return redirect(url_for('import.google_sheets_import'))

            sheets_source = GoogleSheetsDataSource(sheet_id, range_name)
            df = sheets_source.get_content()

        else:
            flash('Invalid source type', 'error')
            return redirect(url_for('import.index'))

        # Check for formatting issues
        issues = check_formatting_issues(df)

        # Convert DataFrame to HTML for display
        table_html = df.to_html(classes='table table-striped', index=False)

        return render_template(
            'import/preview.html',
            table_html=table_html,
            issues=issues,
            source_type=source_type,
            can_import=(len(issues) == 0)
        )

    except Exception as e:
        flash(f'Error previewing data: {str(e)}', 'error')
        return redirect(url_for('import.index'))


@import_bp.route('/import-data', methods=['POST'])
@login_required
def import_data():
    """
    Import data into the database.
    """
    source_type = request.form.get('source_type')

    try:
        df = None

        if source_type == 'csv':
            file_path = session.get('csv_file_path')
            if not file_path or not os.path.exists(file_path):
                flash('CSV file not found', 'error')
                return redirect(url_for('import.csv_import'))

            csv_source = CSVDataSource(file_path)
            df = csv_source.get_content()

        elif source_type == 'google_sheets':
            sheet_id = session.get('sheet_id')
            range_name = session.get('range_name')

            if not sheet_id:
                flash('Google Sheet information not found', 'error')
                return redirect(url_for('import.google_sheets_import'))

            sheets_source = GoogleSheetsDataSource(sheet_id, range_name)
            df = sheets_source.get_content()

        else:
            flash('Invalid source type', 'error')
            return redirect(url_for('import.index'))

        # Check for formatting issues
        issues = check_formatting_issues(df)

        if issues:
            flash('Cannot import data with formatting issues', 'error')
            return redirect(url_for('import.preview', source_type=source_type))

        # Import data into the database
        db_source = DatabaseDataSource()
        import_count = import_to_database(df, db_source, current_user.id)

        flash(f'Successfully imported {import_count} content items', 'success')
        return redirect(url_for('content.index'))

    except Exception as e:
        flash(f'Error importing data: {str(e)}', 'error')
        return redirect(url_for('import.index'))


def check_formatting_issues(df):
    """
    Check for formatting issues in the data.

    Args:
        df: DataFrame to check

    Returns:
        List of formatting issues
    """
    issues = []

    # Check required columns
    required_columns = ['publish_date', 'platform', 'content']
    for col in required_columns:
        if col not in df.columns:
            issues.append(f"Missing required column: {col}")

    # If required columns are missing, return early
    if len(issues) > 0:
        return issues

    # Check for empty values in required columns
    for col in required_columns:
        if df[col].isnull().any():
            issues.append(f"Column '{col}' has empty values")

    # Check platform values
    valid_platforms = ['twitter', 'linkedin', 'substack']
    invalid_platforms = df[~df['platform'].isin(valid_platforms)]['platform'].unique()
    if len(invalid_platforms) > 0:
        issues.append(f"Invalid platform values: {', '.join(invalid_platforms)}")

    # Check if title is provided for Substack
    if 'substack' in df['platform'].values:
        if 'title' not in df.columns:
            issues.append("Column 'title' is required for Substack content")
        elif df[df['platform'] == 'substack']['title'].isnull().any():
            issues.append("Substack content requires a title")

    # Check publish_date format
    try:
        pd.to_datetime(df['publish_date'])
    except:
        issues.append("Invalid date format in 'publish_date' column")

    # Check content length for Twitter (280 characters max)
    if 'twitter' in df['platform'].values:
        twitter_content = df[df['platform'] == 'twitter']['content']
        for i, content in enumerate(twitter_content):
            if len(content) > 280:
                issues.append(f"Twitter content at row {i+2} exceeds 280 characters")

    return issues


def import_to_database(df, db_source, author_id):
    """
    Import data into the database.

    Args:
        df: DataFrame with content data
        db_source: DatabaseDataSource instance
        author_id: ID of the author (current user)

    Returns:
        Number of imported items
    """
    import_count = 0

    for _, row in df.iterrows():
        # Extract data from row
        platform = row['platform']
        content = row['content']
        publish_date = row['publish_date']
        title = row.get('title')
        subtitle = row.get('subtitle')
        url = row.get('url')
        publish_time = row.get('publish_time', '09:00')

        # Add to database
        content_id = db_source.add_content(
            platform=platform,
            content=content,
            publish_date=publish_date,
            title=title,
            subtitle=subtitle,
            url=url,
            publish_time=publish_time,
            author_id=author_id,
            is_draft=True  # Default to draft so user can review before publishing
        )

        if content_id:
            import_count += 1

    return import_count
