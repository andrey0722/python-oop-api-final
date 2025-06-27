"""Communication with the Yandex.Disk API at https://cloud-api.yandex.net/v1.

The API documentation is available at https://yandex.ru/dev/disk-api/doc/ru/.

"""


import time
from typing import Iterable


class YandexDiskApi:
    """A class which instance communicates with the Yandex.Disk API v1."""

    API_ROOT_DEFAULT = 'https://cloud-api.yandex.net/v1'

    # Clause 2.2 of the Yandex.Disk API terms of use:
    # https://yandex.ru/legal/disk_api/ru/#2-usloviya-ispolzovaniya-servisa
    MAX_REQUESTS_PER_SECOND = 40

    # A number of seconds after which a completed request must be deleted
    # from the request history
    HISTORY_EXPIRE_PERIOD = 2.0

    # A number of seconds to sleep when the user hit API request rate limit.
    # A low value will yield more requests in total within API rate limits.
    # A high value will give less CPU usage at cost of lower request rate.
    REQUEST_RATE_SLEEP_PERIOD = 0.1

    def __init__(
        self,
        oauth_key: str,
        *,
        api_root: str = API_ROOT_DEFAULT,
        limit_per_second: int = MAX_REQUESTS_PER_SECOND
    ):
        """Initialize a Yandex.Disk API instance.

        Args:
            oauth_key (str): Yandex.Disk personal API key acquired from
                https://yandex.ru/dev/disk/poligon/.
            api_root (str): Optional override for the API root URL.
            limit_per_second (int): Optional override for the API request
                rate limit per second.
        """
        self._oauth_key = oauth_key
        self._api_root = api_root
        self._limit_per_second = limit_per_second
        self._request_history: list[float] = []

    @property
    def requests_per_second(self) -> int:
        """A number of requests performed during last second."""
        self._clear_expired_requests()
        return self._count_history(1)

    def _register_request(self):
        """Internal helper to register a new request in request history."""
        self._request_history.append(time.time())

    def _get_history_for_period(
        self,
        period_secs: float = HISTORY_EXPIRE_PERIOD
    ) -> Iterable[float]:
        """Internal helper to extract request records from last `period_secs`.

        Args:
            period_secs (float): The number of seconds from
                the current time into the past.

        Returns:
            Iterable[float]: Request records within
                last `period_secs` seconds.
        """
        now = time.time()

        def filter_predicate(request_record: float):
            """Filter out requests that are older than `period_secs`."""
            return request_record + period_secs >= now

        return filter(filter_predicate, self._request_history)

    def _clear_expired_requests(self):
        """Internal helper to delete all expired requests from the history.

        All requests with execution time before `HISTORY_EXPIRE_PERIOD`
        seconds ago will be deleted.
        """
        self._request_history = list(self._get_history_for_period())

    def _count_history(
        self,
        period_secs: float = HISTORY_EXPIRE_PERIOD
    ) -> int:
        """Internal helper to count not expired request records.

        Args:
            period_secs (float): The number of seconds from
                the current time into the past.

        Returns:
            int: The number of requests records within
                last `period_secs` seconds.
        """
        return sum(1 for _ in self._get_history_for_period(period_secs))

    def _wait_for_api_limits(
        self,
        sleep_period: float = REQUEST_RATE_SLEEP_PERIOD
    ):
        """Internal helper to avoid violating API rate limits.

        Sleep for `sleep_period` seconds until current request rate
        is back within specified API rate limit.

        Args:
            sleep_period (float): The number of seconds to sleep
                when the user hit API request rate limit.
        """
        while self.requests_per_second >= self._limit_per_second:
            # Ensure we don't violate per-second limit
            time.sleep(sleep_period)
