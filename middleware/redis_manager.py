from datetime import datetime

from django.core.cache import cache

from middleware.utils import get_current_truncated_utc_z


class RedisManager:
    def push_to_redis(self, queue_name, item, expiry=60 * 30, curr_time=None):
        """
        Push an item to a Redis.

        expiry: in secs
        """
        if not curr_time:
            curr_time = get_current_truncated_utc_z()

        redis_key = f"{queue_name}_{curr_time}"
        cache.set(redis_key, item, timeout=expiry)

    def get_redis_items(self, queue_name):
        """
        Get a range of items from the queue without removing them.
        """

        search_pattern = f"{queue_name}*"
        matching_keys = cache.keys(search_pattern)
        # cleaned_keys = [key.decode().split(":", 2)[-1] for key in matching_keys]
        sorted_keys = sorted(
            matching_keys,
            key=lambda k: datetime.strptime(
                k.split(f"{queue_name}_")[1], "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        )
        response_list = []
        for sorted_key in sorted_keys:
            statuses = cache.get(sorted_key)
            if statuses:
                timestamp = sorted_key.split(f"{queue_name}_")[1]
                response_list.append({"time": timestamp, "status": statuses})

        return response_list


# Create a global instance
redis_manager = RedisManager()
