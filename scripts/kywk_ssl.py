"""TLS configuration shared by the Kywk updater and task commands."""

import os
import ssl


def create_https_context():
    """Use OS trust roots, bundled public roots, and optional custom CA roots."""
    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        certifi = None
    if certifi is not None:
        context.load_verify_locations(cafile=certifi.where())
    custom_ca = os.environ.get("SSL_CERT_FILE")
    if custom_ca:
        context.load_verify_locations(cafile=custom_ca)
    return context
