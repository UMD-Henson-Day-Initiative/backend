"""Gunicorn configuration for Henson Backend."""
import multiprocessing
import os

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count()))
worker_class = "sync"
worker_connections = 1000
timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Application
raw_env = []
