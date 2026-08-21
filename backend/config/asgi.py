import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Plain Django ASGI app for Phase 2. Channels routing (ProtocolTypeRouter,
# WebSocket URLRouter, ticket-authenticated middleware per the Phase 1
# architecture doc, Section 8) is introduced in Phase 9.
application = get_asgi_application()
