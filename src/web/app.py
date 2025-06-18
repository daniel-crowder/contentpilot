"""
Web application entry point.
"""
import os
from flask import Flask, redirect, url_for

from . import app as flask_app
from ..database.setup import init_db

def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        Flask application
    """
    # Initialize database
    init_db()
    
    # Set up routes
    @flask_app.route('/')
    def index():
        """
        Redirect to dashboard or login page.
        """
        return redirect(url_for('dashboard.index'))
    
    return flask_app

def run_app(host='0.0.0.0', port=5000, debug=False):
    """
    Run the Flask application.
    
    Args:
        host: Host to run on
        port: Port to run on
        debug: Whether to run in debug mode
    """
    app = create_app()
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_app(debug=True)