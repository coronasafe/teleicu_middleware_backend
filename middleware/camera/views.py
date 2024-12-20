import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from middleware.camera.exceptions import (
    CameraLockedException,
    InvalidCameraCredentialsException,
)
from middleware.camera.onvif_zeep_camera_controller import OnvifZeepCameraController
from middleware.camera.types import (
    CameraAsset,
    CameraAssetMoveRequest,
    CameraAssetPresetRequest,
    MovementResponse,
    PresetsResponse,
    SanpshotResponse,
    StatusResponseModel,
)
from middleware.camera.utils import cam_params, is_camera_locked
from middleware.redis_manager import redis_manager
from middleware.types import StatusResponse

logger = logging.getLogger(__name__)


@extend_schema(tags=["Camera Operations"])
class CameraViewSet(viewsets.ViewSet):
    @extend_schema(
        summary="Get Camera Status",
        description="Retrieve the status of the camera based on provided hostname, port, username, and password.",
        parameters=cam_params,
        responses={200: StatusResponseModel},
    )
    @action(detail=False, methods=["get"])
    def status(self, request):
        cam_request = CameraAsset(
            hostname=str(request.query_params["hostname"]),
            port=int(request.query_params["port"]),
            username=str(request.query_params["username"]),
            password=str(request.query_params["password"]),
        )
        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        response = cam.get_status()
        return Response(response, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=cam_params,
        responses={200: PresetsResponse},
        description="Retrieve the camera presets.",
    )
    @action(detail=False, methods=["get"])
    def presets(self, request):
        cam_request = CameraAsset(
            hostname=str(request.GET.get("hostname")),
            port=int(request.GET.get("port")),
            username=str(request.GET.get("username")),
            password=str(request.GET.get("password")),
        )
        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        presets = cam.get_presets()
        return Response(presets, status=status.HTTP_200_OK)

    @extend_schema(
        request=CameraAssetPresetRequest,
        responses={200: "string"},
        description="Set a preset",
    )
    @action(detail=False, methods=["post"], url_name="presets")
    def set_preset(self, request):
        cam_request = CameraAssetPresetRequest.model_validate(request.data)
        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        result = cam.set_preset(preset_name=cam_request.preset_name)
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        request=CameraAssetPresetRequest,
        responses={200: "string"},
        description="go to a particular preset",
    )
    @action(detail=False, methods=["post"], url_path="gotoPreset")
    def go_to_preset(self, request):
        cam_request = CameraAssetPresetRequest.model_validate(request.data)
        self.check_camera_state(device_id=cam_request.hostname, raise_error=True)
        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        response = cam.go_to_preset(preset_id=cam_request.preset)
        if not response:
            response = f"Preset {cam_request.preset} Not Found"
            return Response(response, status=status.HTTP_404_NOT_FOUND)
        return Response(response, status=status.HTTP_200_OK)

    @extend_schema(
        request=CameraAssetMoveRequest,
        responses={200: MovementResponse},
        description="Perform an abosulte move",
    )
    @action(detail=False, methods=["post"], url_path="absoluteMove")
    def absolute_move(self, request):
        cam_request = CameraAssetMoveRequest.model_validate(request.data)
        self.return_if_camera_locked(device_id=cam_request.hostname, raise_error=True)

        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        cam.absolute_move(pan=cam_request.x, tilt=cam_request.y, zoom=cam_request.zoom)
        return Response(
            {"status": "success", "message": "Camera position updated!"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CameraAssetMoveRequest,
        responses={200: MovementResponse},
        description="Perform a Relative move",
    )
    @action(detail=False, methods=["post"], url_path="relativeMove")
    def relative_move(self, request):
        cam_request = CameraAssetMoveRequest.model_validate(request.data)
        self.return_if_camera_locked(device_id=cam_request.hostname, raise_error=True)

        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        cam.relative_move(pan=cam_request.x, tilt=cam_request.y, zoom=cam_request.zoom)
        return Response(
            {"status": "success", "message": "Camera position updated!"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CameraAssetMoveRequest,
        responses={200: SanpshotResponse},
        description="Get Sanpshot uri at a particular position",
    )
    @action(detail=False, methods=["post"], url_path="snapshotAtLocation")
    def snapshot_at_location(self, request):
        cam_request = CameraAssetMoveRequest.model_validate(request.data)
        self.return_if_camera_locked(device_id=cam_request.hostname, raise_error=True)
        cam: OnvifZeepCameraController = self.get_camera_controller(cam_request)
        cam.relative_move(pan=cam_request.x, tilt=cam_request.y, zoom=cam_request.zoom)
        snapshot_uri = cam.get_snapshot_uri()
        return Response(
            {"status": "success", "uri": snapshot_uri},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: StatusResponse},
        description="Get statuses for camera devices",
    )
    @action(detail=False, methods=["get"], url_path="cameras/status")
    def camera_statuses(self, request):
        statuses = redis_manager.get_redis_items(settings.CAMERA_STATUS_KEY)
        return Response(statuses, status=status.HTTP_200_OK)

    def _check_camera_state(self, device_id, raise_error=False):
        state = is_camera_locked(device_id)

        if state and raise_error:
            raise CameraLockedException

    def return_if_camera_locked(self, device_id, raise_error=False):
        try:
            self._check_camera_state(device_id=device_id, raise_error=raise_error)
        except CameraLockedException:
            logger.debug("Camera with host: %s is locked.", device_id)
            return Response(
                {
                    "message": "Camera is Locked!",
                },
                status=status.HTTP_423_LOCKED,
            )

    def get_camera_controller(self, camera_request):
        try:
            return OnvifZeepCameraController(req=camera_request)

        except InvalidCameraCredentialsException as exc:
            logger.error("An exception occurred while getting presets: %s", exc)
            return Response(
                {"message": exc.default_detail}, status=status.HTTP_400_BAD_REQUEST
            )
