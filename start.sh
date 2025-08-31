#!/bin/bash
# Render sets $PORT automatically
exec gunicorn --bind 0.0.0.0:$PORT property_manager_improved_app:app
