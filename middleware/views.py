from datetime import datetime
from django.conf import settings
from django.shortcuts import render
import requests
from rest_framework.decorators import api_view

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework import viewsets, status
from rest_framework.decorators import action
from django.db import connection
from django.db.utils import OperationalError
from middleware.models import Asset
from middleware.utils import _get_headers, generate_jwt


class MiddlewareHealthViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def ping(self, request):
        return Response({"pong": datetime.now()}, status=status.HTTP_200_OK)

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


@api_view(["POST"])
def get_mock_request_list(request):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "send_mock_req", {"type": "send_mock_req", "message": request.data}
    )
    return Response({"result": "Received request"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def verify_token(request):
    token = request.data["token"]

    if not token:
        return Response(
            {"error": "no token provided"}, status=status.HTTP_401_UNAUTHORIZED
        )
    res = requests.post(settings.CARE_VERIFY_TOKEN_URL, data={"token": token})
    res.raise_for_status()
    middleware_token = generate_jwt(exp=60 * 20)
    return Response({"token": {middleware_token}}, status=status.HTTP_200_OK)


def home(request):
    return render(request, "index.html")
