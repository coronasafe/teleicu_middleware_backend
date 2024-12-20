from datetime import datetime

from pydantic import BaseModel


class StatusResponse(BaseModel):
    time: datetime
    status: dict[str, str]


class VerifyTokenRequest(BaseModel):
    Token: str


class VerifyTokenResponse(BaseModel):
    Token: str


class PingResponse(BaseModel):
    pong: datetime


class HealthCheckResponse(BaseModel):
    server: bool
    database: bool
