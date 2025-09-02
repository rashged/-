#!/bin/bash
exec gunicorn -w 4 -b 0.0.0.0:$PORT property_manager_improved_app:app
