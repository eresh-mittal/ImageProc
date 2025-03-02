#!/bin/bash
set -e

# Start Redis in the background
redis-server --daemonize yes

# Start Celery worker in the background
celery -A tasks worker --loglevel=info --detach

# Start the Flask application with Gunicorn
gunicorn --bind 0.0.0.0:5000 app:app