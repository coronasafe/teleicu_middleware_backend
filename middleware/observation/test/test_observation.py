from unittest import TestCase as UnitTest
from unittest.mock import MagicMock, call, patch

from middleware.observation.test.util_factory import ObservationFactory
from middleware.observation.types import ObservationID
from middleware.observation.views import (
    blood_pressure_data,
    flatten_observations,
    store_and_send_observations,
    update_blood_pressure,
)


class TestObservation(UnitTest):
    def test_update_blood_pressure(self):
        observation_1 = ObservationFactory(observation_id=ObservationID.BLOOD_PRESSURE)
        observation_2 = ObservationFactory(
            observation_id=ObservationID.BODY_TEMPERATURE1
        )

        list_of_observation = [observation_1, observation_2]
        update_blood_pressure(list_of_observation)
        self.assertEqual(blood_pressure_data[observation_1.device_id], observation_1)
        with self.assertRaises(KeyError):
            blood_pressure_data[observation_2.device_id]

    def test_flatten_observations(self):
        observation_1 = ObservationFactory()
        observation_2 = ObservationFactory()
        observation_3 = ObservationFactory()
        observation_4 = ObservationFactory()
        observation_5 = ObservationFactory()

        nested_list = [
            observation_1,
            observation_2,
            [observation_3, [observation_4, [observation_5]]],
        ]

        flattened_list = flatten_observations(nested_list)
        self.assertEqual(5, len(flattened_list))

    @patch("middleware.observation.views.get_channel_layer")
    @patch("middleware.observation.views.async_to_sync")
    def test_store_and_send_observations(
        self, mock_async_to_sync, mock_get_channel_layer
    ):
        device_1_observation_1 = ObservationFactory(device_id="1")
        device_1_observation_2 = ObservationFactory(device_id="1")
        device_2_observation_1 = ObservationFactory(device_id="2")
        device_2_observation_2 = ObservationFactory(device_id="2")

        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        observation_list = [
            device_1_observation_1.model_dump(mode="json", by_alias=True),
            device_1_observation_2.model_dump(mode="json", by_alias=True),
            device_2_observation_1.model_dump(mode="json", by_alias=True),
            device_2_observation_2.model_dump(mode="json", by_alias=True),
        ]

        store_and_send_observations(data=observation_list)
        self.assertEqual(2, mock_async_to_sync.call_count)

        expected_calls = [
            call(mock_channel_layer.group_send),
            call()(
                "ip_1",
                {
                    "type": "send_observation",
                    "message": [
                        device_1_observation_1.model_dump(mode="json", by_alias=True),
                        device_1_observation_2.model_dump(mode="json", by_alias=True),
                    ],
                },
            ),
            call(mock_channel_layer.group_send),
            call()(
                "ip_2",
                {
                    "type": "send_observation",
                    "message": [
                        device_2_observation_1.model_dump(mode="json", by_alias=True),
                        device_2_observation_2.model_dump(mode="json", by_alias=True),
                    ],
                },
            ),
        ]
        mock_async_to_sync.assert_has_calls(expected_calls, any_order=True)

    @patch("middleware.observation.views.get_channel_layer")
    @patch("middleware.observation.views.async_to_sync")
    def test_observations_without_blood_pressure(
        self, mock_async_to_sync, mock_get_channel_layer
    ):
        """Test to check if the data for previous blood pressure is passed to the web socket consumers if blood pressure is not present"""
        device_1_observation_1 = ObservationFactory(
            device_id="1", observation_id=ObservationID.BLOOD_PRESSURE
        )
        device_1_observation_2 = ObservationFactory(
            device_id="1", observation_id=ObservationID.BODY_TEMPERATURE1
        )
        update_blood_pressure([device_1_observation_1])

        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        store_and_send_observations(
            data=[device_1_observation_2.model_dump(mode="json", by_alias=True)]
        )

        self.assertEqual(1, mock_async_to_sync.call_count)

        expected_call = [
            call(mock_channel_layer.group_send),
            call()(
                "ip_1",
                {
                    "type": "send_observation",
                    "message": [
                        device_1_observation_2.model_dump(mode="json", by_alias=True),
                        device_1_observation_1.model_dump(mode="json", by_alias=True),
                    ],
                },
            ),
        ]
        mock_async_to_sync.assert_has_calls(expected_call)
