from typing import Dict, Optional

from pydantic import AliasChoices, BaseModel, Field

from middleware.observation.types import DeviceID


class CameraAsset(BaseModel):
    hostname: str
    username: str
    password: str
    port: int
    useSecure: Optional[bool] = None


class CameraAssetPresetRequest(CameraAsset):
    preset: int = Field(
        default=None, validation_alias=AliasChoices("preset", "presetName")
    )


class CameraAssetMoveRequest(CameraAsset):
    x: float
    y: float
    zoom: float


class CameraStatus:
    time: str
    status: Dict[DeviceID, str]


class MoveStatusResponse(BaseModel):
    panTilt: str
    zoom: str


class CameraAssetStatusResponse(BaseModel):
    x: float
    y: float
    zoom: float


class StatusResponseModel(BaseModel):
    position: CameraAssetStatusResponse
    moveStatus: MoveStatusResponse
    error: str


class PresetsResponse(BaseModel):
    presets: Dict[str, int]


class MovementResponseMessage(BaseModel):
    status: str
    messsage: str


class MovementResponse(BaseModel):
    result: MovementResponseMessage


class SanpshotResponse(BaseModel):
    status: str
    uri: str
