"""Communication with the Yandex.Disk API at https://cloud-api.yandex.net/v1.

The API documentation is available at https://yandex.ru/dev/disk-api/doc/ru/.

"""


import requests
import time
from typing import Iterable, override


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

    def create_directory(
        self,
        dir_path: str,
        *,
        ignore_existing: bool = True
    ):
        """Create a directory in YD cloud storage.

        Args:
            dir_path (str): A valid YD path of the directory to create.
            ignore_existing (bool): If True, ignore the error in the case
                when the directory already exists.

        Raises:
            HTTPError: an error occured while accessing YD server.
        """
        self._wait_for_api_limits()
        self._register_request()
        url = f'{self._api_root}/disk/resources'
        headers = self._get_common_headers()
        params = {
            'path': dir_path,
        }
        response = requests.put(url, headers=headers, params=params)
        self._raise_error(response, 409, ignore_existing)

    def delete_item(
        self,
        item_path: str,
        *,
        permanently: bool = True,
        ignore_non_existent: bool = True
    ):
        """Delete a file or directory from YD cloud storage.

        Args:
            item_path (str): A valid YD path of the item to delete.
            permanently (bool): If False, move the item to Recycle Bin.
                If True, delete the item permanently from YD storage.
            ignore_non_existent (bool): If True, ignore the error in
                the case when the item don't exist.

        Raises:
            HTTPError: an error occured while accessing YD server.
        """
        self._wait_for_api_limits()
        self._register_request()
        url = f'{self._api_root}/disk/resources'
        headers = self._get_common_headers()
        params = {
            'path': item_path,
            'permanently': permanently,
        }
        response = requests.delete(url, headers=headers, params=params)
        self._raise_error(response, 404, ignore_non_existent)

    def upload_file_from_url(self, file_path: str, upload_url: str):
        """Create a file in YD storage and fill it with data from URL.

        Does not access the URL locally, YD directly uploads it, so
        no extra overheads are added.

        Args:
            file_path (str): A valid YD path of the file to upload to.
            upload_url (str): An URL to upload the data from.

        Raises:
            HTTPError: an error occured while accessing YD server.
        """
        self._wait_for_api_limits()
        self._register_request()
        url = f'{self._api_root}/disk/resources/upload'
        headers = self._get_common_headers()
        params = {
            'url': upload_url,
            'path': file_path,
        }
        response = requests.post(url, headers=headers, params=params)
        self._raise_error(response)

    def check_item_exists(self, item_path: str) -> bool:
        """Check whether an item exists in YD cloud storage.

        Args:
            item_path (str): A valid YD path of the item to check.

        Raises:
            HTTPError: an error occured while accessing YD server.
        """
        self._wait_for_api_limits()
        self._register_request()
        url = f'{self._api_root}/disk/resources'
        headers = self._get_common_headers()
        params = {
            'path': item_path,
        }
        response = requests.delete(url, headers=headers, params=params)
        self._raise_error(response, 404, True)  # Suppress error 404
        return response.status_code != 404

    def _get_common_headers(self) -> dict[str, str]:
        """Internal helper to construct common headers for HTTP requests."""
        return {
            'Authorization': f'OAuth {self._oauth_key}',
            'Accept': 'application/json',
        }

    def _raise_error(
        self,
        response: requests.Response,
        suppress_code: int = 0,
        suppress_flag: bool = False
    ):
        """Internal helper to raise an error from HTTP response with
        an option to suppress it.

        Args:
            response (requests.Response): The response from HTTP request.
            suppress_code (int): A suppressable HTTP status code. If
                the actual status code doesn't match, then the code
                is not suppressed.
            suppress_flag (bool): If True, then suppress the error with
                status code `suppress_code`.

        Raises:
            HTTPError: an error occured while accessing YD server.
        """
        if response.status_code != suppress_code or not suppress_flag:
            response.raise_for_status()

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


class YandexDiskApiDummy(YandexDiskApi):
    """A dummy for testing purposes."""

    DUMMY_DELAY = 0.02

    @property
    def requests_per_second(self) -> int:
        time.sleep(type(self).DUMMY_DELAY)
        return 0

    @override
    def create_directory(
        self,
        dir_path: str,
        *,
        ignore_existing: bool = True
    ):
        time.sleep(type(self).DUMMY_DELAY)

    @override
    def delete_item(
        self,
        item_path: str,
        *,
        permanently: bool = True,
        ignore_non_existent: bool = True
    ):
        time.sleep(type(self).DUMMY_DELAY)

    @override
    def upload_file_from_url(self, file_path: str, upload_url: str):
        time.sleep(type(self).DUMMY_DELAY)

    @override
    def check_item_exists(self, item_path: str) -> bool:
        time.sleep(type(self).DUMMY_DELAY)
        return False
