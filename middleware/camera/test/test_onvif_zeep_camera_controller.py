from unittest import TestCase as UnitTest
from unittest.mock import MagicMock, patch

from middleware.camera.exceptions import InvalidCameraCredentialsException
from middleware.camera.onvif_zeep_camera_controller import OnvifZeepCameraController
from middleware.camera.types import CameraAsset


class TestOnvifZeepCameraController(UnitTest):
    @patch("middleware.camera.onvif_zeep_camera_controller.ONVIFCamera")
    def setUp(self, mocked_onvif_camera):
        # Mock the ONVIFCamera and its services
        self.mock_camera = mocked_onvif_camera.return_value
        self.mock_media_service = MagicMock()
        self.mock_ptz_service = MagicMock()
        self.mock_camera.create_media_service.return_value = self.mock_media_service
        self.mock_camera.create_ptz_service.return_value = self.mock_ptz_service

        mock_status = MagicMock()
        mock_status.MoveStatus.PanTilt = "IDLE"
        mock_status.MoveStatus.Zoom = "IDLE"

        self.mock_ptz_service.GetStatus.return_value = mock_status

        # Mock the media profile
        self.mock_profile = MagicMock()
        self.mock_profile.token = "test_token"
        self.mock_media_service.GetProfiles.return_value = [self.mock_profile]

        # Create a CameraAsset instance
        req = CameraAsset(
            hostname="test_hostname", port=80, username="user", password="pass"
        )

        # Initialize the controller with the mocked ONVIFCamera
        self.cam = OnvifZeepCameraController(req)

    def test_get_presets(self):
        # Mock the GetPresets response
        self.mock_ptz_service.GetPresets.return_value = [
            MagicMock(Name="Preset1"),
            MagicMock(Name="Preset2"),
        ]

        expected_presets = {"Preset1": 0, "Preset2": 1}
        actual_presets = self.cam.get_presets()

        self.assertEqual(actual_presets, expected_presets)

    def test_go_to_preset(self):
        # Mock the GetPresets response
        self.mock_ptz_service.GetPresets.return_value = [
            MagicMock(Name="Preset1", token="token1"),
            MagicMock(Name="Preset2", token="token2"),
        ]

        result = self.cam.go_to_preset("Preset1")
        self.assertEqual(result, "Preset1")

    def test_get_status(self):
        # Mock the GetStatus response
        mock_status = MagicMock()
        mock_status.Position.PanTilt.x = 1.0
        mock_status.Position.PanTilt.y = 2.0
        mock_status.Position.Zoom.x = 3.0
        self.mock_ptz_service.GetStatus.return_value = mock_status

        expected_status = {"x": 1.0, "y": 2.0, "zoom": 3.0}
        actual_status = self.cam.get_status()

        self.assertEqual(actual_status, expected_status)

    def test_absolute_move(self):
        self.cam.absolute_move(1.0, 2.0, 3.0)
        self.mock_ptz_service.AbsoluteMove.assert_called_once()

    def test_relative_move(self):
        self.cam.relative_move(1.0, 2.0, 3.0)
        self.mock_ptz_service.RelativeMove.assert_called_once()

    def test_set_preset(self):
        # Mock the GetPresets response
        self.mock_ptz_service.GetPresets.return_value = []
        self.cam.set_preset("NewPreset")
        self.mock_ptz_service.SetPreset.assert_called_once()

    def test_get_snapshot_uri(self):
        # Mock the GetSnapshotUri response
        mock_response = MagicMock()
        mock_response.Uri = "http://example.com/snapshot.jpg"
        self.mock_media_service.GetSnapshotUri.return_value = mock_response

        actual_uri = self.cam.get_snapshot_uri()
        self.assertEqual(actual_uri, "http://example.com/snapshot.jpg")


class CameraExceptions(UnitTest):
    def setUp(self):
        self.req = CameraAsset(
            hostname="112.334.23.12",
            username="test_user",
            password="test_pass",
            port="80",
        )

    def test_raise_exception_when_conn_error(self):
        with self.assertRaisesRegex(
            InvalidCameraCredentialsException, "Invalid Credentials"
        ):
            OnvifZeepCameraController(self.req)
