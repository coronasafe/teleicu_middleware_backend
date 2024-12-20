from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    summary="Retrieve the OpenID Connect configuration",
    description="This endpoint provides the public JSON Web Keys (JWKs) required for validating tokens signed by the middleware. The response is cached for 24 hours.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kty": {"type": "string", "example": "RSA"},
                            "kid": {"type": "string", "example": "1234abcd"},
                            "use": {"type": "string", "example": "sig"},
                            "n": {"type": "string", "example": "modulus"},
                            "e": {"type": "string", "example": "exponent"},
                        },
                    },
                },
            },
        },
    },
)
class PublicJWKsView(GenericAPIView):
    """
    Retrieve the OpenID Connect configuration
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @method_decorator(cache_page(60 * 60 * 24))
    def get(self, *args, **kwargs):
        return Response(settings.JWKS.as_dict())
