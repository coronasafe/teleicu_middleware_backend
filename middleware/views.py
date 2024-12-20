import requests
from django.conf import settings
from django.utils import timezone
from django.db import connection
from django.db.utils import OperationalError
from django.shortcuts import render
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from middleware.models import Asset
from middleware.types import (
    HealthCheckResponse,
    PingResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from middleware.utils import _get_headers, generate_jwt


@extend_schema_view(
    ping=extend_schema(description="Ping the server to check if it's up."),
    health_check=extend_schema(
        description="Check the health status of the server and database."
    ),
    care_communication_check=extend_schema(
        description="Check communication with the CARE API."
    ),
    care_communication_check_as_asset=extend_schema(
        description="Check communication with the CARE API for a specific asset."
    ),
)
class MiddlewareHealthViewSet(viewsets.ViewSet):
    @extend_schema(
        responses={200: PingResponse},
    )
    @action(detail=False, methods=["get"])
    def ping(self, request):
        return Response({"pong": timezone.now()}, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: HealthCheckResponse},
    )
    @action(detail=False, methods=["get"], url_path="status")
    def health_check(self, request):
        server = True
        database = False

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = True
        except OperationalError:
            pass

        status_code = 200 if server and database else 500

        return Response({"server": server, "database": database}, status=status_code)

    @extend_schema(
        responses={200: str},
    )
    @action(detail=False, methods=["get"], url_path="care/communication")
    def care_communication_check(self, request):
        try:
            headers = _get_headers()
            response = requests.get(
                f"{settings.CARE_API}/middleware/verify", headers=headers
            )
            response.raise_for_status()
            return Response(response.content, content_type="application/json")
        except requests.RequestException as error:
            return Response(
                {"error": str(error.response.text if error.response else error)},
                status=500,
            )

    @extend_schema(
        responses={200: str},
    )
    @action(detail=False, methods=["get"], url_path="care/communication-asset")
    def care_communication_check_as_asset(self, request):
        ip = request.GET.get("ip")
        ext_id = request.GET.get("ext_id")

        if ip or ext_id:
            asset = (
                Asset.objects.filter(deleted=False).filter(ip_address=ip)
                | Asset.objects.filter(id=ext_id).first()
            )
        else:
            asset = Asset.objects.filter(deleted=False).first()

        if asset is None:
            return Response({"error": "No active asset found"}, status=404)

        try:
            headers = _get_headers(claims={"asset_id": str(asset.id)})
            response = requests.get(
                f"{settings.CARE_API}/middleware/verify-asset", headers=headers
            )
            response.raise_for_status()
            return Response(response.content, content_type="application/json")
        except requests.RequestException as error:
            return Response(
                {"error": str(error.response.text if error.response else error)},
                status=500,
            )


@extend_schema(
    request=VerifyTokenRequest,
    responses={200: VerifyTokenResponse},
    description="Endpoint to very care jwt tokens",
)
@api_view(["POST"])
def verify_token(request):
    request = VerifyTokenRequest.model_validate(request.data)

    if not request.Token:
        return Response(
            {"error": "no token provided"}, status=status.HTTP_401_UNAUTHORIZED
        )
    res = requests.post(settings.CARE_VERIFY_TOKEN_URL, data={"token": request.Token})
    res.raise_for_status()
    middleware_token = generate_jwt(exp=60 * 20)
    return Response({"token": {middleware_token}}, status=status.HTTP_200_OK)


def home(request):
    return render(request, "index.html")
