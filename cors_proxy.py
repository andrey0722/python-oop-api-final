"""This module contains definitions of CORS proxy classes
to use with BasicWebApi class.
"""

from typing import Any, Iterable, override

import urllib.parse
import requests

from web_api import CORSProxy, WebApiLimit


class CorsAnywhereProxy(CORSProxy):
    """Defines a CORS proxy at https://github.com/Rob--W/cors-anywhere."""

    @property
    def headers(self) -> dict[str, Any]:
        return {'Origin': 'null'}

    @property
    def limits(self) -> Iterable[WebApiLimit]:
        return (WebApiLimit(period=1, rate_limit=10),)

    @override
    def construct_url(self, url: str) -> str:
        return f'https://cors-anywhere.herokuapp.com/{url}'


class ThingCorsProxy(CORSProxy):
    """Defines a CORS proxy at https://github.com/Freeboard/thingproxy."""

    @property
    def limits(self) -> Iterable[WebApiLimit]:
        return (WebApiLimit(period=1, rate_limit=10),)

    @override
    def construct_url(self, url: str) -> str:
        return f'https://thingproxy.freeboard.io/fetch/{url}'


class BridgedCorsProxy(CORSProxy):
    """Defines a CORS proxy at https://cors.sh/.

    Requires an API key to operate correctly.
    """

    def __init__(self, api_key: str):
        """Intialize a Bridged CORS proxy instance.

        Args:
            api_key (str): Bridged CORS proxy API key.
        """
        super().__init__()
        self._api_key = api_key

    @property
    def headers(self) -> dict[str, Any]:
        return {'Origin': 'null', 'x-cors-api-key': self._api_key}

    @override
    def construct_url(self, url: str) -> str:
        return f'https://proxy.cors.sh/{url}'


class AllOriginsCorsProxy(CORSProxy):
    """Defines a CORS proxy at https://allorigins.win/."""

    @property
    def limits(self) -> Iterable[WebApiLimit]:
        return (WebApiLimit(period=2, rate_limit=1),)

    @override
    def construct_url(self, url: str) -> str:
        encoded = urllib.parse.urlencode({'url': url})
        return f'https://api.allorigins.win/get?{encoded}'

    @override
    def process_response(self, response: requests.Response):
        if response.ok:
            # Proxy sends the actual status code inside a JSON, while
            # responding itself with 200. We must unpack the response.
            proxy_result: dict[str, Any] = response.json()

            # The actual status code
            response.status_code = proxy_result['status']['http_code']

            # Replace request's content with the actual content
            text: str = proxy_result['contents']
            content = text.encode(response.apparent_encoding)
            # Override response's internal field
            response._content = content  # pylint: disable=W0212
