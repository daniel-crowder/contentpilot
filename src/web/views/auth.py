"""
Authentication views for the web application.
"""
import os
import secrets
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from ...database.setup import get_session, close_session
from ...database.models import User, PlatformCredential
from ..auth import authenticate_user, create_user
from ...platforms.linkedin import LinkedInPlatform
from ...platforms.wordpress import WordPressPlatform

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page.
    """
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Handle login form submission
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form

        # Authenticate user
        user = authenticate_user(username, password)

        if user:
            # Log in user
            login_user(user, remember=remember)

            # Redirect to requested page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Logout page.
    """
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration page.
    """
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Handle registration form submission
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        # Validate form data
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html')

        # Create user
        user_id = create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        if user_id:
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Username or email already exists', 'error')

    return render_template('auth/register.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    User profile page.
    """
    session = get_session()

    try:
        user = session.query(User).filter(User.id == current_user.id).first()

        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard.index'))

        # Get LinkedIn credentials
        linkedin_credential = session.query(PlatformCredential).filter(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform == 'linkedin'
        ).first()

        linkedin_connected = False
        linkedin_expires_at = None

        if linkedin_credential:
            linkedin_connected = True
            linkedin_expires_at = linkedin_credential.expires_at

            # Check if the token is expired
            if linkedin_credential.is_expired():
                linkedin_connected = False
                flash('Your LinkedIn connection has expired. Please reconnect.', 'warning')

        # Get WordPress credentials
        wordpress_credential = session.query(PlatformCredential).filter(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform == 'wordpress'
        ).first()

        wordpress_connected = False
        wordpress_expires_at = None
        wordpress_blog_url = None

        if wordpress_credential:
            wordpress_connected = True
            wordpress_expires_at = wordpress_credential.expires_at

            # Extract blog URL from scope if available
            if wordpress_credential.scope and 'blog_url:' in wordpress_credential.scope:
                wordpress_blog_url = wordpress_credential.scope.split('blog_url:')[1].split(',')[0]

            # Check if the token is expired
            if wordpress_credential.expires_at and wordpress_credential.is_expired():
                wordpress_connected = False
                flash('Your WordPress connection has expired. Please reconnect.', 'warning')

        # Handle profile form submission
        if request.method == 'POST':
            # Update user data
            user.first_name = request.form.get('first_name')
            user.last_name = request.form.get('last_name')

            # Update password if provided
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if new_password:
                if new_password != confirm_password:
                    flash('Passwords do not match', 'error')
                    return render_template('auth/profile.html', 
                                          user=user,
                                          linkedin_connected=linkedin_connected,
                                          linkedin_expires_at=linkedin_expires_at,
                                          wordpress_connected=wordpress_connected,
                                          wordpress_expires_at=wordpress_expires_at,
                                          wordpress_blog_url=wordpress_blog_url)

                user.password_hash = generate_password_hash(new_password)

            session.commit()
            flash('Profile updated successfully', 'success')

        return render_template('auth/profile.html', 
                              user=user,
                              linkedin_connected=linkedin_connected,
                              linkedin_expires_at=linkedin_expires_at,
                              wordpress_connected=wordpress_connected,
                              wordpress_expires_at=wordpress_expires_at,
                              wordpress_blog_url=wordpress_blog_url)

    finally:
        close_session(session)


@auth_bp.route('/linkedin/authorize')
@login_required
def linkedin_authorize():
    """
    Initiate the LinkedIn OAuth 2.0 authorization code flow.
    """
    # Generate a random state parameter for CSRF protection
    state = secrets.token_hex(16)
    session['linkedin_oauth_state'] = state

    # Create LinkedIn platform instance
    linkedin = LinkedInPlatform(redirect_uri=url_for('auth.linkedin_callback', _external=True))

    # Generate the authorization URL
    auth_url = linkedin.get_authorization_url(
        scopes=['r_liteprofile', 'w_member_social'],
        state=state
    )

    # Redirect to the authorization URL
    return redirect(auth_url)


@auth_bp.route('/wordpress/authorize')
@login_required
def wordpress_authorize():
    """
    Initiate the WordPress.com OAuth 2.0 authorization code flow.
    """
    # Generate a random state parameter for CSRF protection
    state = secrets.token_hex(16)
    session['wordpress_oauth_state'] = state

    # Get client ID and client secret from environment variables
    client_id = os.environ.get('WORDPRESS_CLIENT_ID')
    client_secret = os.environ.get('WORDPRESS_CLIENT_SECRET')

    if not client_id or not client_secret:
        flash('WordPress OAuth2 credentials are not configured', 'error')
        return redirect(url_for('auth.profile'))

    # Create WordPress platform instance
    wordpress = WordPressPlatform(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=url_for('auth.wordpress_callback', _external=True),
        use_oauth=True
    )

    # Generate the authorization URL
    try:
        auth_url = wordpress.get_authorization_url(
            scopes=['global'],
            state=state
        )

        # Redirect to the authorization URL
        return redirect(auth_url)
    except Exception as e:
        flash(f'Error initiating WordPress authorization: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))


@auth_bp.route('/linkedin/callback')
@login_required
def linkedin_callback():
    """
    Handle the callback from LinkedIn OAuth 2.0 authorization.
    """
    # Get the authorization code and state from the request
    code = request.args.get('code')
    state = request.args.get('state')

    # Verify the state parameter to prevent CSRF attacks
    if not state or state != session.get('linkedin_oauth_state'):
        flash('Invalid state parameter. Please try again.', 'error')
        return redirect(url_for('auth.profile'))

    # Clear the state from the session
    session.pop('linkedin_oauth_state', None)

    # If no code was received, show an error
    if not code:
        flash('No authorization code received from LinkedIn', 'error')
        return redirect(url_for('auth.profile'))

    try:
        # Create LinkedIn platform instance
        linkedin = LinkedInPlatform(redirect_uri=url_for('auth.linkedin_callback', _external=True))

        # Exchange the authorization code for an access token
        token_data = linkedin.exchange_code_for_token(code)

        # Extract token information
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in')  # Seconds until expiration

        if not access_token:
            flash('Failed to obtain access token from LinkedIn', 'error')
            return redirect(url_for('auth.profile'))

        # Calculate expiration date
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None

        # Store the token in the database
        db_session = get_session()
        try:
            # Check if a credential already exists for this user and platform
            credential = db_session.query(PlatformCredential).filter(
                PlatformCredential.user_id == current_user.id,
                PlatformCredential.platform == 'linkedin'
            ).first()

            if credential:
                # Update existing credential
                credential.access_token = access_token
                credential.token_type = token_data.get('token_type')
                credential.expires_at = expires_at
                credential.scope = token_data.get('scope')
                credential.updated_at = datetime.utcnow()
            else:
                # Create new credential
                credential = PlatformCredential(
                    user_id=current_user.id,
                    platform='linkedin',
                    access_token=access_token,
                    token_type=token_data.get('token_type'),
                    expires_at=expires_at,
                    scope=token_data.get('scope')
                )
                db_session.add(credential)

            db_session.commit()
            flash('LinkedIn account connected successfully', 'success')
        except Exception as e:
            db_session.rollback()
            flash(f'Error storing LinkedIn credentials: {str(e)}', 'error')
        finally:
            close_session(db_session)

        return redirect(url_for('auth.profile'))

    except Exception as e:
        flash(f'Error connecting to LinkedIn: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))


@auth_bp.route('/wordpress/callback')
@login_required
def wordpress_callback():
    """
    Handle the callback from WordPress.com OAuth 2.0 authorization.
    """
    # Get the authorization code and state from the request
    code = request.args.get('code')
    state = request.args.get('state')

    # Verify the state parameter to prevent CSRF attacks
    if not state or state != session.get('wordpress_oauth_state'):
        flash('Invalid state parameter. Please try again.', 'error')
        return redirect(url_for('auth.profile'))

    # Clear the state from the session
    session.pop('wordpress_oauth_state', None)

    # If no code was received, show an error
    if not code:
        flash('No authorization code received from WordPress', 'error')
        return redirect(url_for('auth.profile'))

    try:
        # Get client ID and client secret from environment variables
        client_id = os.environ.get('WORDPRESS_CLIENT_ID')
        client_secret = os.environ.get('WORDPRESS_CLIENT_SECRET')

        if not client_id or not client_secret:
            flash('WordPress OAuth2 credentials are not configured', 'error')
            return redirect(url_for('auth.profile'))

        # Create WordPress platform instance
        wordpress = WordPressPlatform(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=url_for('auth.wordpress_callback', _external=True),
            use_oauth=True
        )

        # Exchange the authorization code for an access token
        token_data = wordpress.exchange_code_for_token(code)

        # Extract token information
        access_token = token_data.get('access_token')

        if not access_token:
            flash('Failed to obtain access token from WordPress', 'error')
            return redirect(url_for('auth.profile'))

        # WordPress tokens don't typically have an expiration, but we'll set one for 60 days just in case
        expires_at = datetime.utcnow() + timedelta(days=60)

        # Extract blog information
        blog_id = token_data.get('blog_id')
        blog_url = token_data.get('blog_url')

        # Create a scope string that includes blog information
        scope = 'global'
        if blog_id:
            scope += f',blog_id:{blog_id}'
        if blog_url:
            scope += f',blog_url:{blog_url}'

        # Create token_data JSON
        token_data_json = json.dumps({
            'blog_id': blog_id,
            'blog_url': blog_url
        })

        # Store the token in the database
        db_session = get_session()
        try:
            # Check if a credential already exists for this user and platform
            credential = db_session.query(PlatformCredential).filter(
                PlatformCredential.user_id == current_user.id,
                PlatformCredential.platform == 'wordpress'
            ).first()

            if credential:
                # Update existing credential
                credential.access_token = access_token
                credential.token_type = 'oauth2'
                credential.expires_at = expires_at
                credential.scope = scope
                credential.token_data = token_data_json
                credential.updated_at = datetime.utcnow()
            else:
                # Create new credential
                credential = PlatformCredential(
                    user_id=current_user.id,
                    platform='wordpress',
                    access_token=access_token,
                    token_type='oauth2',
                    expires_at=expires_at,
                    scope=scope,
                    token_data=token_data_json
                )
                db_session.add(credential)

            db_session.commit()
            flash('WordPress account connected successfully', 'success')
        except Exception as e:
            db_session.rollback()
            flash(f'Error storing WordPress credentials: {str(e)}', 'error')
        finally:
            close_session(db_session)

        return redirect(url_for('auth.profile'))

    except Exception as e:
        flash(f'Error connecting to WordPress: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))
