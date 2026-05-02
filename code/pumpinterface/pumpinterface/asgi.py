import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import scanner.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pumpinterface.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            scanner.routing.websocket_urlpatterns
        )
    ),
})