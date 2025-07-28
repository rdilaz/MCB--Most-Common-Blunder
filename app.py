"""
MCB - Most Common Blunder Analysis
Refactored Flask Application using modular architecture.
Based on app_production.py for production-ready features.

This is the new main application file that replaces the monolithic app.py.
It uses the new modular structure with production security and optimizations.
"""
import os
import logging
from flask import Flask
from dotenv import load_dotenv

from config import DEBUG_MODE, PORT, LOGGING_CONFIG
from routes import create_app

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format']
)
logger = logging.getLogger(__name__)

# Create the Flask app at module level for gunicorn
app = create_app()

def main():
    """Main entry point for the application with production features."""
    try:
        
        # Log startup message
        logger.info("=" * 60)
        logger.info("🎯 MCB - Most Common Blunder Analysis (Production)")
        logger.info("🚀 Starting refactored application with security features...")
        logger.info(f"🌐 Server will run on {'0.0.0.0' if not DEBUG_MODE else '127.0.0.1'}:{PORT}")
        logger.info(f"🔒 Security features: {'ENABLED' if not DEBUG_MODE else 'DEVELOPMENT MODE'}")
        logger.info(f"📊 Rate limiting: {'ENABLED' if not DEBUG_MODE else 'DEVELOPMENT MODE'}")
        logger.info("=" * 60)
        
        # Production settings
        host = '0.0.0.0' if not DEBUG_MODE else '127.0.0.1'
        
        # Run the application
        app.run(
            debug=DEBUG_MODE,
            port=PORT,
            host=host,
            threaded=True,
            use_reloader=DEBUG_MODE
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise

if __name__ == '__main__':
    main() 