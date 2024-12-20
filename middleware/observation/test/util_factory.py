from datetime import datetime

import factory

from middleware.observation.types import (
    BloodPressure,
    Interpretation,
    Observation,
    ObservationID,
    Status,
    WaveName,
)


class BloodPressureFactory(factory.Factory):
    class Meta:
        model = BloodPressure

    value = factory.Faker("pyfloat", positive=True, min_value=60, max_value=200)
    unit = "mmHg"
    interpretation = Interpretation.NORMAL
    low_limit = factory.Faker("pyfloat", positive=True, min_value=60, max_value=90)
    high_limit = factory.Faker("pyfloat", positive=True, min_value=120, max_value=180)


class ObservationFactory(factory.Factory):
    class Meta:
        model = Observation

    observation_id = ObservationID.WAVEFORM
    device_id = factory.Faker("uuid4")
    date_time = factory.LazyFunction(datetime.now)
    patient_name = factory.Faker("name")
    status = Status.CONNECTED
    patient_id = factory.Sequence(lambda n: str(1 + n % 100))
    value = factory.Faker("pyfloat", positive=True)
    unit = factory.Faker("random_element", elements=("mmHg", "bpm", "%"))
    interpretation = Interpretation.NORMAL
    low_limit = factory.Faker("pyfloat", positive=True)
    high_limit = factory.Faker("pyfloat", positive=True)
    systolic = factory.SubFactory(BloodPressureFactory)
    diastolic = factory.SubFactory(BloodPressureFactory)
    map = factory.SubFactory(BloodPressureFactory)
    wave_name = WaveName.PLETH
    resolution = factory.Faker("random_element", elements=("1", "0.1", "0.01"))
    sampling_rate = factory.Faker("random_element", elements=("125", "250", "500"))
    data_baseline = factory.Faker("pyfloat")
    data_low_limit = factory.Faker("pyfloat")
    data_high_limit = factory.Faker("pyfloat")
    data = factory.Faker("pystr")
    taken_at = factory.LazyFunction(datetime.now)
