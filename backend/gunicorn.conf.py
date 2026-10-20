"""One process is required by the application's Sheet idempotency lock."""

import os


bind = '0.0.0.0:' + os.environ.get('PORT', '10000')
workers = 1
worker_class = 'gthread'
threads = 4
timeout = 120
preload_app = False
# Avoid logging request lines, query strings, client addresses, or form details.
accesslog = None
errorlog = '-'
loglevel = 'info'
