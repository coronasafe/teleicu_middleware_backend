import logging

import jwt
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from pydantic import ValidationError
from requests import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action, authentication_classes

from middleware.authentication import CareAuthentication
from middleware.stream.types import (
    StreamResponse,
    VerifyStreamTokenRequest,
    VideoStreamRequest,
    VitalSteamRequest,
)
from middleware.utils import generate_jwt

logger = logging.getLogger(__name__)


@extend_schema_view(
    get_video_feed_stream_token=extend_schema(
        description="Get a jwt token for camera video stream"
    ),
    get_vital_stream_token=extend_schema(
        description="Get a jwt token for vital stream"
    ),
    validate_stream_token=extend_schema(
        description="Verify the tokens generated for streams"
    ),
)
class MiddlewareStreamViewSet(viewsets.ViewSet):
    @extend_schema(
        request=VideoStreamRequest,
        responses={200: StreamResponse},
    )
    @action(detail=False, methods=["post"], url_path="getToken/videoFeed")
    @authentication_classes([CareAuthentication])
    def get_video_feed_stream_token(self, request):
        try:
            request = VideoStreamRequest.model_validate(request)
        except ValidationError:
            return Response(
                {"message": "stream and ip are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        duration = int(request._duration if request._duration else "5")
        if duration < 0 or duration > 60:
            return Response(
                {"message": "duration must be between 0 and 60"}, status=400
            )
        middleware_token = generate_jwt(
            claims={"stream": request.stream, "ip": request.ip}, exp=60 * duration
        )

        return Response({"token": {middleware_token}}, status=status.HTTP_200_OK)

    @extend_schema(
        request=VitalSteamRequest,
        responses={200: StreamResponse},
    )
    @action(detail=False, methods=["post"], url_path="getToken/vitals")
    @authentication_classes([CareAuthentication])
    def get_vital_stream_token(self, request):
        try:
            request = VitalSteamRequest.model_validate(request)
        except ValidationError:
            return Response(
                {"message": "asset_id and ip are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        duration = int(request._duration if request._duration else "5")
        if duration < 0 or duration > 60:
            return Response(
                {"message": "duration must be between 0 and 60"}, status=400
            )
        middleware_token = generate_jwt(
            claims={"asset_id": request.asset_id, "ip": request.ip}, exp=60 * duration
        )

        return Response({"token": {middleware_token}}, status=status.HTTP_200_OK)

    @extend_schema(
        request=VerifyStreamTokenRequest,
        responses={200: StreamResponse},
    )
    @action(detail=False, methods=["post"], url_path="verifyToken")
    def validate_stream_token(self, request):
        try:
            request = VerifyStreamTokenRequest.model_validate(request)
        except ValidationError:
            return Response(
                {"message": "token, stream, and ip are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            # Decode the token
            key = settings.JWKS.as_dict()["keys"][0]
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            value = jwt.decode(request.token, key=public_key, algorithms=["RS256"])
            decoded_value = VerifyStreamTokenRequest.model_validate(value)

            if decoded_value.ip == request.ip or decoded_value.stream == request.stream:
                return Response({"status": 1}, status=status.HTTP_200_OK)

            return Response({"status": 0}, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as exc:
            logger.info("Token Expired with error: %s", exc)
            return Response(
                {"message": exc.errors()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
