"""This module contains definitions of base classes for communicating
Web APIs using HTTP requests.
"""

import json
import time
from typing import Any, Iterable, NamedTuple, Set

import requests


def extract_base_name(uri: str):
    """Extract a base file name from a specified `uri`."""
    uri = uri.split('?')[0]    # Strip possible ?query component
    uri = uri.split('#')[0]    # Strip possible #fragment component
    return uri.split('/')[-1]  # Extract the last component in URI path


class WebApiLimit(NamedTuple):
    """Describes generic API request rate limit. The specified rate limit
    must be respected during the specified time period in seconds.
    """
    period: float
    rate_limit: int


class BasicWebApi:
    """A class which instance communicates with Web API and keeps its
    request rate within limit.
    """

    # Default values for some parameters
    REQUEST_HISTORY_EXPIRE_DEFAULT = 2.0
    RATE_LIMIT_SLEEP_DEFAULT = 0.1

    # Recommended by Requests docs:
    # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
    REQUEST_TIMEOUT_DEFAULT = (3.05, 27.0)

    def __init__(
        self,
        api_root: str,
        *,
        oauth_key: str | None = None,
        api_limits: Iterable[WebApiLimit] | None = None,
        rate_limit_sleep: float = RATE_LIMIT_SLEEP_DEFAULT,
        request_history_expire: float = REQUEST_HISTORY_EXPIRE_DEFAULT,
        request_timeout: float | tuple[float, float] = REQUEST_TIMEOUT_DEFAULT
    ):
        """Initialize an API instance.

        Args:
            api_root (str): API root URL.
            oauth_key (str): OAuth key to use in requests to this API.
                None means no OAuth authorization is needed.
            api_limits (Iterable[WebApiLimit] | None): API request rate
                limits per specified period. None means no rate limit
                for this API.
            rate_limit_sleep (float): A number of seconds to sleep when
                the user hit API request rate limit. A low value will
                yield more requests in total within API rate limits.
                A high value will give less CPU usage at cost of lower
                request rate.
            request_history_expire (float): A number of seconds
                after which a completed request must be deleted
                from the request history.
        """
        self._api_root = api_root
        self._oauth_key = oauth_key
        self._api_limits = list(api_limits) if api_limits else []
        self._rate_limit_sleep = rate_limit_sleep
        self._request_history_expire = request_history_expire
        self._request_timeout = request_timeout
        self._request_history: list[float] = []
        self._session = requests.Session()

    def __enter__(self):
        """Do nothing."""
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Close the session."""
        self.close()

    def close(self):
        """Close the session."""
        self._session.close()

    def get_rate_per_period(self, period: float) -> int:
        """Return number of requests performed during time period.

        Args:
            period (float): Time period in seconds.
        """
        self._clear_expired_requests()
        return self._count_history(period)

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        suppress: Set[int] | None = None
    ) -> requests.Response:
        """Perform an HTTP request to API endpoint with parameters.

        HTTP request is constructed from the input parameters and sent
        to the HTTP server. Any HTTP error will be raised unless explicitly
        suppressed using the `suppress` parameter.

        Args:
            method (str): A valid HTTP request type.
            endpoint (str): A path relative to the API root URL.
            params (dict[str, Any] | None): Request parameters that
                must be encoded inside request URL.
            headers (dict[str, Any] | None): Additional HTTP headers
                to use in the request.
            suppress (Set[int] | None): Optional parameter
                to suppress errors with specific HTTP status codes.
                If the status code is contained in `suppress` then
                this error must be suppressed. None means no
                suppression setting is used.

        Raises:
            HTTPError: an error occurred during HTTP request.
        """
        self._wait_for_api_limits()

        # Prepare the request parameters
        url = f'{self._api_root}/{endpoint}'
        headers = self._construct_headers(headers)

        # Perform the request
        self._register_request()
        response = self._session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            timeout=self._request_timeout
        )
        self._raise_error(response, suppress)
        return response

    def _construct_headers(
        self,
        headers: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Internal helper to prepare input HTTP headers before handing
        over to `requests.request()`.

        Args:
            headers (dict[str, Any] | None): Input HTTP headers.
        """
        result = self._get_common_headers()
        if headers is not None:
            result.update(headers)
        return result

    def _get_common_headers(self) -> dict[str, Any]:
        """Internal helper to construct common headers for HTTP requests."""
        headers = {
            'Accept': 'application/json',
            "Connection": "keep-alive",
            "Keep-Alive": "timeout=60",
        }
        if self._oauth_key is not None:
            headers['Authorization'] = f'OAuth {self._oauth_key}'
        return headers

    def _raise_error(
        self,
        response: requests.Response,
        suppress: Set[int] | None = None
    ):
        """Internal helper to raise an error from HTTP response with
        an option to suppress it.

        Args:
            response (requests.Response): The response from HTTP request.
            suppress (Set[int] | None): A set containing HTTP status
                codes to suppress. None means no suppress setting.

        Raises:
            HTTPError: an error occurred during HTTP request.
        """
        if suppress is None or response.status_code not in suppress:
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                # Append response message to the exception
                e.add_note(self._get_response_message(response))
                raise

    def _get_response_message(self, response: requests.Response) -> str:
        """Return a message string from HTTP response.

        Args:
            response (requests.Response): The response from HTTP request.
        """
        try:
            return json.dumps(response.json(), indent=4, ensure_ascii=False)
        except json.JSONDecodeError:
            return response.text

    def _register_request(self):
        """Internal helper to register a new request in request history."""
        self._request_history.append(time.time())

    def _get_history_for_period(self, period_secs: float) -> Iterable[float]:
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

        All requests with execution time before `self._request_history_expire`
        seconds ago will be deleted.
        """
        period = self._request_history_expire
        self._request_history = list(self._get_history_for_period(period))

    def _count_history(self, period_secs: float) -> int:
        """Internal helper to count not expired request records.

        Args:
            period_secs (float): The number of seconds from
                the current time into the past.

        Returns:
            int: The number of requests records within
                last `period_secs` seconds.
        """
        return sum(1 for _ in self._get_history_for_period(period_secs))

    def _wait_for_api_limits(self):
        """Internal helper to avoid violating API all rate limits.

        Sleep for `self._rate_limit_sleep` seconds until current
        request rate is back within specified API rate limit.
        """
        # Respect the rate limits sequentially
        for limit in self._api_limits:
            while self.get_rate_per_period(limit.period) >= limit.rate_limit:
                # Ensure we don't violate specified limit per period
                time.sleep(self._rate_limit_sleep)
