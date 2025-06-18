"""
Web application package for the Social Media Content Publisher.
"""
import os
from flask import Flask
from flask_login import LoginManager

# Create Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Import and register blueprints
from .views.auth import auth_bp
from .views.content import content_bp
from .views.dashboard import dashboard_bp
from .views.teams import teams_bp
from .views.analytics import analytics_bp
from .views.import_data import import_bp

app.register_blueprint(auth_bp)
app.register_blueprint(content_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(teams_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(import_bp)

# Import user loader
from .auth import load_user

# Set up user loader
@login_manager.user_loader
def user_loader(user_id):
    return load_user(user_id)
