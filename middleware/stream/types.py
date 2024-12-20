from typing import Optional

from pydantic import BaseModel


class StreamRequestModel(BaseModel):
    ip: str
    _duration: Optional[str]


class VideoStreamRequest(StreamRequestModel):
    stream: str


class VitalSteamRequest(StreamRequestModel):
    asset_id: str


class VerifyStreamTokenRequest(BaseModel):
    token: str
    ip: str
    stream: str


class StreamResponse(BaseModel):
    message: str
