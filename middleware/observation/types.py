from datetime import datetime
from enum import Enum
from typing import Dict, List, NewType, Optional

from django.utils.timezone import now
from pydantic import BaseModel, Field, RootModel, field_serializer

DeviceID = NewType("DeviceID", str)


class ObservationID(str, Enum):
    HEART_RATE = "heart-rate"
    ST = "ST"
    SPO2 = "SpO2"
    PULSE_RATE = "pulse-rate"
    RESPIRATORY_RATE = "respiratory-rate"
    BODY_TEMPERATURE1 = "body-temperature1"
    BODY_TEMPERATURE2 = "body-temperature2"
    BLOOD_PRESSURE = "blood-pressure"
    WAVEFORM = "waveform"
    DEVICE_CONNECTION = "device-connection"
    WAVEFORM_II = "waveform_II"
    WAVEFORM_PLETH = "waveform_Pleth"
    WAVEFORM_RESPIRATION = "waveform_Respiration"


class Status(str, Enum):
    FINAL = "final"
    LEADS_OFF = "Message-Leads Off"
    MEASUREMENT_INVALID = "Message-Measurement Invalid"
    TACHY_CARDIA = "Message-Tachy Cardia"
    PROBE_UNPLUGGED = "Message-Probe Unplugged"
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"


class Interpretation(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    NA = "NA"


class WaveName(str, Enum):
    II = "II"
    PLETH = "Pleth"
    RESPIRATION = "Respiration"


class BloodPressure(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    interpretation: Optional[Interpretation] = None
    low_limit: Optional[float] = Field(default=None, alias="low-limit")
    high_limit: Optional[float] = Field(default=None, alias="high-limit")


def get_current_time():
    return now()


class Observation(BaseModel):
    observation_id: ObservationID
    device_id: str
    date_time: datetime = Field(alias="date-time")
    patient_id: str = Field(alias="patient-id")
    patient_name: Optional[str] = Field(default=None, alias="patient-name")
    status: Optional[Status] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    interpretation: Optional[Interpretation] = None
    low_limit: Optional[float] = Field(default=None, alias="low-limit")
    high_limit: Optional[float] = Field(default=None, alias="high-limit")
    systolic: Optional[BloodPressure] = None
    diastolic: Optional[BloodPressure] = None
    map: Optional[BloodPressure] = None
    wave_name: Optional[WaveName] = Field(default=None, alias="wave-name")
    resolution: Optional[str] = None
    sampling_rate: Optional[str] = Field(default=None, alias="sampling rate")
    data_baseline: Optional[float] = Field(default=None, alias="data-baseline")
    data_low_limit: Optional[float] = Field(default=None, alias="data-low-limit")
    data_high_limit: Optional[float] = Field(default=None, alias="data-high-limit")
    data: Optional[str] = None
    taken_at: datetime = Field(exclude=True, default_factory=get_current_time)

    @field_serializer("date_time")
    def serialize_dt(self, dt: datetime, _info):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        populate_by_name = True


class ObservationList(RootModel):
    root: List[Observation]


class BloodPressureDailyRound(BaseModel):
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    # mean: Optional[float] = None


class DailyRoundObservation(BaseModel):
    spo2: Optional[float] = None
    ventilator_spo2: Optional[float] = None
    resp: Optional[float] = None
    pulse: Optional[float] = None
    temperature: Optional[float] = None
    temperature_measured_at: Optional[datetime] = None
    bp: Optional[BloodPressureDailyRound] = {}
    taken_at: Optional[datetime] = None
    rounds_type: Optional[str] = None
    is_parsed_by_ocr: Optional[bool] = None


class StaticObservation(BaseModel):
    observations: Dict[ObservationID, List[Observation]]
    last_updated: datetime


class MonitorOptions(BaseModel):
    slug: str
    options: Optional[Dict]


class DataDumpRequest(BaseModel):
    data: List[Observation]
    key: str
    monitor_options: MonitorOptions
