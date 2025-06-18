#!/usr/bin/env python3
"""
Web application runner for the Social Media Content Publisher.
"""
import argparse
from src.web.app import run_app

def main():
    """
    Main entry point for the web application.
    """
    parser = argparse.ArgumentParser(description='Social Media Content Publisher Web Interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run on')
    parser.add_argument('--port', type=int, default=5400, help='Port to run on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting web server on {args.host}:{args.port}...")
    run_app(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()