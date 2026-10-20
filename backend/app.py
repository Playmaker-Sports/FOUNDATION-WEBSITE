"""Foundation-only scholarship API. No tournament/Ops services are imported."""

import logging

from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from foundation_scholarships import register_scholarship_routes


logger = logging.getLogger(__name__)
MAX_REQUEST_BYTES = 128 * 1024


def create_app(config=None, **scholarship_adapters):
    application = Flask(__name__, static_folder=None)
    application.config.update(MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES)
    if config:
        application.config.update(config)

    # Render terminates TLS and supplies the final proxy hop. Trust one hop for
    # client IP/protocol only; do not trust forwarded host or prefix headers.
    application.wsgi_app = ProxyFix(application.wsgi_app, x_for=1, x_proto=1)
    limiter = Limiter(
        get_remote_address, app=application, storage_uri='memory://',
        default_limits=['60 per minute'],
    )
    application.extensions['foundation_limiter'] = limiter

    @application.get('/health')
    @limiter.exempt
    def health():
        # Liveness for Render or an external ping. This never opens Google,
        # sends email, reads credentials, or claims intake is configured.
        return jsonify(status='ok', service='foundation-scholarship-api')

    @application.errorhandler(HTTPException)
    def http_error(error):
        message = 'Please shorten your responses and try again.' if error.code == 413 else error.name
        return jsonify(success=False, message=message), error.code

    @application.errorhandler(Exception)
    def unexpected_error(error):
        # Exception text/tracebacks can contain submitted answers or credentials.
        logger.error('Foundation request failed [%s]', type(error).__name__)
        return jsonify(success=False, message='The application service is temporarily unavailable.'), 500

    @application.after_request
    def response_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    register_scholarship_routes(application, limiter, **scholarship_adapters)
    return application


app = create_app()
