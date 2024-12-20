import functools
import logging
from time import sleep

from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter

from middleware.observation.types import DeviceID

logger = logging.getLogger(__name__)

cam_params = [
    OpenApiParameter(
        name="hostname", description="Camera hostname", required=True, type=str
    ),
    OpenApiParameter(name="port", description="Camera port", required=True, type=int),
    OpenApiParameter(
        name="username", description="Camera username", required=True, type=str
    ),
    OpenApiParameter(
        name="password", description="Camera password", required=True, type=str
    ),
]


def wait_for_movement_completion(func):
    @functools.wraps(func)
    def wrapper_wait_for_movement_completion(self, *args, **kwargs):
        response = func(self, *args, **kwargs)

        # Poll the status of the camera's movement
        while True:
            status = self.camera_ptz.GetStatus(
                {"ProfileToken": self.camera_media_profile.token}
            )
            # Assuming 'Moving' is a boolean attribute indicating movement status
            if status.MoveStatus.PanTilt == "IDLE" and status.MoveStatus.Zoom == "IDLE":
                logger.info("Movement completed.")
                break

            # Sleep for a short period before checking the status again
            sleep(0.5)
        return response

    return wrapper_wait_for_movement_completion


def lock_camera(ip: DeviceID):
    cache.set(f"{settings.CAMERA_LOCK_KEY}{ip}", True, settings.CAMERA_LOCK_TIMEOUT)


def unlock_camera(ip: DeviceID):
    cache.delete(f"{settings.CAMERA_LOCK_KEY}{ip}")


def is_camera_locked(ip: DeviceID):
    return cache.get(f"{settings.CAMERA_LOCK_KEY}{ip}")
