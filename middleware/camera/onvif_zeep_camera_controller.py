import logging

from django.conf import settings
from onvif import ONVIFCamera, ONVIFError

from middleware.camera.abstract_camera import AbstractCameraController
from middleware.camera.exceptions import InvalidCameraCredentialsException
from middleware.camera.types import CameraAsset
from middleware.camera.utils import wait_for_movement_completion

logger = logging.getLogger(__name__)


class OnvifZeepCameraController(AbstractCameraController):
    def __init__(self, req: CameraAsset) -> None:
        try:
            cam = ONVIFCamera(
                req.hostname, req.port, req.username, req.password, settings.WSDL_PATH
            )
        except ONVIFError as err:
            logger.debug(
                "Exception raised while connecting to Camera with req: %s and reason: %s",
                req,
                err.reason,
            )

            raise InvalidCameraCredentialsException

        media = cam.create_media_service()

        logger.debug("Create ptz service object")
        ptz = cam.create_ptz_service()

        logger.debug("Get profiles")
        media_profile = media.GetProfiles()[0]

        self.cam = cam
        self.camera_ptz = ptz
        self.camera_media_profile = media_profile
        self.camera_media = media

    def get_presets(self):
        ptz_get_presets = self.get_complete_preset()
        logger.debug("camera_command( get_preset() )")

        presets = {}
        for i, preset in enumerate(ptz_get_presets):
            presets[preset.Name] = i
        return presets

    def get_complete_preset(self):
        request = self.camera_ptz.create_type("GetPresets")
        request.ProfileToken = self.camera_media_profile.token
        ptz_get_presets = self.camera_ptz.GetPresets(request)
        return ptz_get_presets

    @wait_for_movement_completion
    def go_to_preset(self, preset_id: int):
        preset_list = self.get_complete_preset()
        request = self.camera_ptz.create_type("GotoPreset")
        request.ProfileToken = self.camera_media_profile.token
        logger.debug("camera_command go_to_preset:%s ", preset_id)
        for id, preset in enumerate(preset_list):
            if preset_id == id:
                request.PresetToken = preset.token
                self.camera_ptz.GotoPreset(request)
                return preset.Name
        logger.warning("Preset: %s  not found!", id)
        return None

    def get_status(self):
        request = self.camera_ptz.create_type("GetStatus")
        request.ProfileToken = self.camera_media_profile.token
        ptz_status = self.camera_ptz.GetStatus(request)

        pan = ptz_status.Position.PanTilt.x
        tilt = ptz_status.Position.PanTilt.y
        zoom = ptz_status.Position.Zoom.x
        pan_tilt_status = ptz_status.MoveStatus.PanTilt
        zoom_status = ptz_status.MoveStatus.Zoom
        error = ptz_status.Error
        status = {
            "position": {
                "x": pan,
                "y": tilt,
                "zoom": zoom,
            },
            "moveStatus": {"panTilt": pan_tilt_status, "zoom": zoom_status},
            "error": error,
        }
        return status

    @wait_for_movement_completion
    def absolute_move(self, pan: float, tilt: float, zoom: float):
        request = self.camera_ptz.create_type("AbsoluteMove")
        request.ProfileToken = self.camera_media_profile.token
        request.Position = {"PanTilt": {"x": pan, "y": tilt}, "Zoom": zoom}
        resp = self.camera_ptz.AbsoluteMove(request)
        logger.debug("camera_command( aboslute_move(%f, %f, %f) )", pan, tilt, zoom)
        return resp

    @wait_for_movement_completion
    def relative_move(self, pan: float, tilt: float, zoom: float):
        request = self.camera_ptz.create_type("RelativeMove")
        request.ProfileToken = self.camera_media_profile.token
        request.Translation = {"PanTilt": {"x": pan, "y": tilt}, "Zoom": zoom}
        resp = self.camera_ptz.RelativeMove(request)
        logger.debug("camera_command( relative_move(%f, %f, %f) )", pan, tilt, zoom)
        return resp

    def set_preset(self, preset_name: str):
        presets = self.get_complete_preset()
        request = self.camera_ptz.create_type("SetPreset")
        request.ProfileToken = self.camera_media_profile.token
        request.PresetName = preset_name
        logger.debug("camera_command( set_preset%s) )", preset_name)

        for _, preset in enumerate(presets):
            if str(preset.Name) == preset_name:
                logger.warning(
                    "Preset ('%s') not created. Preset already exists!", preset_name
                )
                return None

        ptz_set_preset = self.camera_ptz.SetPreset(request)
        logger.debug("Preset ('%s') created!", preset_name)
        return ptz_set_preset

    def get_snapshot_uri(self):
        request = self.camera_media.create_type("GetSnapshotUri")
        request.ProfileToken = self.camera_media_profile.token
        response = self.camera_media.GetSnapshotUri(request)
        return response.Uri
