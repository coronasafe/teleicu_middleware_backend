from datetime import datetime
import logging
from typing import Dict, List, Union
from middleware.types.observations import (
    DailyRoundObservation,
    Observation,
    ObservationID,
    ObservationList,
    Status,
)
import pytz
from django.core.cache import cache
from django.conf import settings
from middleware.types.observations import DeviceID, StaticObservation
logger = logging.getLogger(__name__)

messages = {
    "Leads Off": {
        "description": "ECG leads disconnected",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Asystole": {
        "description": "Arrhythmia - Asystole",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Missed Beat": {
        "description": "Arrhythmia – Missed beat",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Tachy Cardia": {
        "description": "Arrhythmia - Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Brady Cardia": {
        "description": "Arrhythmia – Brady cardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "VFIB": {
        "description": "Arrhythmia - Ventricular Fibrillation",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "VTAC": {
        "description": "Arrhythmia - Ventricular Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "R ON T": {
        "description": "Arrhythmia – R on T",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "COUPLET": {
        "description": "Arrhythmia – PVC couplet",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "BIGEMINY": {
        "description": "Arrhythmia - Bigeminy",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "TRIGEMINY": {
        "description": "Arrhythmia - Trigeminy",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PNC": {
        "description": "Arrhythmia - Premature Nodal contraction",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PNP": {
        "description": "Arrhythmia - Pace not pacing",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "ARRHYTHMIA": {
        "description": "Arrhythmia present, couldn’t detect the specific arrhythmia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Run of PVCs": {
        "description": "Arrhythmia – Run of PVCs",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Premature Beat": {
        "description": "Arrhythmia – Ventricular Premature Beat",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "PVC High": {
        "description": "Arrhythmia – PVC High",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Non Standard Ventricular Tachycardia": {
        "description": "Arrhythmia – Nonstandard Ventricular Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Extreme Tachycardia": {
        "description": "Arrhythmia – Extreme Tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Extreme Bradycardia": {
        "description": "Arrhythmia – Extreme Bradycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Pause": {
        "description": "Arrhythmia – Heart Pause",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Irregular Rhythm": {
        "description": "Arrhythmia – Irregular rhythm",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Bradycardia": {
        "description": "Arrhythmia – Ventricular tachycardia",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Ventricular Rhythm": {
        "description": "Arrhythmia – Ventricular rhythm.",
        "validity": "The HR value is null, if invalid",
        "observationType": "ECG",
    },
    "Wrong cuff": {
        "description": "Wrong cuff for the patient (for example paediatric NIBP being measured using ADULT cuff)",
        "validity": "",
        "observationType": "NIBP",
    },
    "Connect Cuff": {
        "description": "No cuff / loose cuff",
        "validity": "",
        "observationType": "NIBP",
    },
    "Measurement error": {
        "description": "Measurement taken is erroneous",
        "validity": "",
        "observationType": "NIBP",
    },
    "No finger in probe": {
        "description": "SpO2 sensor has fallen off the patient finger",
        "validity": "The SpO2, PR value is invalid if this message is present. Value will be set to null.",
        "observationType": "SPO2",
    },
    "Probe unplugged": {
        "description": "The SPO2 sensor probe is disconnected from the patient monitor.",
        "validity": "The SpO2, PR value is invalid if this message is present. Value will be set to null.",
        "observationType": "SPO2",
    },
    "Leads off": {
        "description": "Respiration leads have fallen off / disconnected from the patient",
        "validity": "The value is null if invalid",
        "observationType": "Respiration",
    },
    "Measurement invalid": {
        "description": "The measured value is invalid",
        "validity": "When this message is present, the measured value is invalid.",
        "observationType": "Temperature",
        "invalid": True,
    },
}


def is_valid(observation: Observation):
    if (
        not observation
        or not observation.status
        or (
            observation.observation_id != ObservationID.BLOOD_PRESSURE
            and not isinstance(observation.value, (int, float))
        )
    ):
        return False

    if observation.status == Status.FINAL:
        return True

    message = observation.status.replace("Message-", "")
    message_obj = messages.get(message, None)
    if message_obj and message_obj.get("invalid"):
        return False

    return True


def get_vitals_from_observations(ip_address: str):

    logger.info("Getting vitals from observations for the asset: %s", ip_address)

    observation: StaticObservation = get_static_observations(device_id=ip_address)
    if (
        not observation
        or (datetime.now() - observation.last_updated).total_seconds() * 1000
        > settings.UPDATE_INTERVAL
    ):
        return None
    data = observation.observations

    temperature_data = get_value_from_data(
        "body-temperature1", data
    ) or get_value_from_data("body-temperature2", data)
    if temperature_data is None:
        temperature_data = {"temperature": None, "temperature_measured_at": None}

    return DailyRoundObservation(
        taken_at=observation.last_updated,
        spo2=get_value_from_data(ObservationID.SPO2, data),
        ventilator_spo2=get_value_from_data(ObservationID.SPO2, data),
        resp=get_value_from_data(ObservationID.RESPIRATORY_RATE, data),
        pulse=get_value_from_data(ObservationID.HEART_RATE, data)
        or get_value_from_data(ObservationID.PULSE_RATE, data),
        **temperature_data,
        bp=get_value_from_data(ObservationID.BLOOD_PRESSURE, data) or {},
        rounds_type="AUTOMATED",
        is_parsed_by_ocr=False
    )


def get_value_from_data(
    type: ObservationID,
    data: Dict[
        ObservationID,
        Union[Observation, List[Observation]],
    ],
):
    if not data or type not in data:
        return None

    observation: Observation = (
        data[type][-1] if isinstance(data[type], list) else data[type]
    )

    if not observation.date_time:
        return None

    ist_timezone = pytz.timezone("Asia/Kolkata")
    converted_date_time = observation.date_time.astimezone(ist_timezone)

    is_stale = (
        pytz.utc.localize(datetime.now()).astimezone(ist_timezone) - converted_date_time
    ).total_seconds() * 1000 > settings.UPDATE_INTERVAL

    if is_stale or not is_valid(observation):
        return None

    if type in [
        ObservationID.BODY_TEMPERATURE1,
        ObservationID.BODY_TEMPERATURE2,
    ]:
        if observation.low_limit < observation.value < observation.high_limit:
            return {
                "temperature": observation.value,
                "temperature_measured_at": converted_date_time.isoformat(),
            }
        return None
    elif type == "blood-pressure":
        return {
            "systolic": observation.systolic.value if observation.systolic else None,
            "diastolic": observation.diastolic.value if observation.diastolic else None,
        }
    else:
        return observation.value


def get_stored_observations():
    observations = cache.get(settings.REDIS_OBSERVATIONS_KEY)
    if observations is None:
        observations = []
        cache.set(settings.REDIS_OBSERVATIONS_KEY, observations)

    return ObservationList.model_validate(observations).root


def update_stored_observations(observation_list: List[Observation]):
    observations = cache.get(settings.REDIS_OBSERVATIONS_KEY)
    if observations is None:
        observations = []
    observations.extend(observation_list)
    cache.set(settings.REDIS_OBSERVATIONS_KEY, observations)


def get_static_observations(device_id: DeviceID):
    observations = cache.get(settings.REDIS_OBSERVATIONS_KEY)
    current_time = datetime.now()
    # last one hour data matching the device id
    valid_observations: List[Observation] = []
    if not observations:
        return None

    for observation in observations:
        parsed_observation = Observation.model_validate(observation)
        if (
            (current_time - parsed_observation.taken_at).total_seconds() * 1000
            < settings.UPDATE_INTERVAL
        ) and parsed_observation.device_id == device_id:
            valid_observations.append(parsed_observation)

    if not valid_observations:
        return None
    return generate_static_observations(observation_list=valid_observations)


def generate_static_observations(observation_list: List[Observation]):
    observations_dict = {}
    for observation in observation_list:
        observation_type = observation.observation_id
        if observation_type in observations_dict:
            observations_dict[observation_type].append(observation)
        else:
            observations_dict[observation_type] = [observation]

    return StaticObservation(
        observations=observations_dict, last_updated=observation_list[-1].taken_at
    )
