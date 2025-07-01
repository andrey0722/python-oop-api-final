"""Communication with the Yandex.Disk API at https://cloud-api.yandex.net/v1.

The API documentation is available at https://yandex.ru/dev/disk-api/doc/ru/.

"""


import time
from typing import Any, Set, override

import requests

from web_api import BasicWebApi


class YandexDiskApi(BasicWebApi):
    """A class which instance communicates with the Yandex.Disk API v1."""

    API_ROOT_DEFAULT = 'https://cloud-api.yandex.net/v1'

    # Clause 2.2 of the Yandex.Disk API terms of use:
    # https://yandex.ru/legal/disk_api/ru/#2-usloviya-ispolzovaniya-servisa
    MAX_REQUESTS_PER_SECOND = 40

    # Sometimes YD storage temporarily locks a resource after an operation.
    # In this case YD API returns error 423 on resource modification attempt.
    # This parameter specifies maximum number of attempts to unlock the
    # resource before giving up.
    MAX_UNLOCK_ATTEMPTS = 20
    UNLOCK_DELAY = 0.2

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
        super().__init__(
            oauth_key=oauth_key,
            api_root=api_root,
            limit_per_second=limit_per_second
        )

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
            HTTPError: an error occurred while accessing YD server.
        """
        params = {
            'path': dir_path,
        }
        suppress = {409} if ignore_existing else None
        self._request(
            'PUT',
            'disk/resources',
            params=params,
            suppress=suppress
        )

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
            HTTPError: an error occurred while accessing YD server.
        """
        params = {
            'path': item_path,
            'permanently': permanently,
        }
        suppress = {404} if ignore_non_existent else None
        self._request(
            'DELETE',
            'disk/resources',
            params=params,
            suppress=suppress
        )

    def upload_file_from_url(self, file_path: str, upload_url: str):
        """Create a file in YD storage and fill it with data from URL.

        Does not access the URL locally, YD directly uploads it, so
        no extra overheads are added.

        Args:
            file_path (str): A valid YD path of the file to upload to.
            upload_url (str): An URL to upload the data from.

        Raises:
            HTTPError: an error occurred while accessing YD server.
        """
        params = {
            'url': upload_url,
            'path': file_path,
        }
        self._request(
            'POST',
            'disk/resources/upload',
            params=params
        )

    def check_item_exists(self, item_path: str) -> bool:
        """Check whether an item exists in YD cloud storage.

        Args:
            item_path (str): A valid YD path of the item to check.

        Raises:
            HTTPError: an error occurred while accessing YD server.
        """
        params = {
            'path': item_path,
        }
        suppress = {404}  # We explicitly check for error 404
        response = self._request(
            'GET',
            'disk/resources',
            params=params,
            suppress=suppress
        )
        return response.status_code != 404

    @override
    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        suppress: Set[int] | None = None
    ) -> requests.Response:
        unlock_suppress = set()
        if suppress is not None:
            unlock_suppress.update(suppress)
        unlock_suppress.add(423)  # Manually handle error 423

        response = super()._request(
            method=method,
            endpoint=endpoint,
            params=params,
            headers=headers,
            suppress=unlock_suppress
        )
        if response.status_code != 423:
            return response

        max_retries = max(type(self).MAX_UNLOCK_ATTEMPTS, 1) - 1
        unlock_delay = type(self).UNLOCK_DELAY

        # Repeat request until the resource is unlocked
        for _ in range(max_retries):
            # Wait between retries
            time.sleep(unlock_delay)
            response = super()._request(
                method=method,
                endpoint=endpoint,
                params=params,
                headers=headers,
                suppress=unlock_suppress
            )
            if response.status_code != 423:
                return response

        # Still locked, giving up. Using user-supplied suppress setting
        # because the user could suppress error 423 beforehand.
        self._raise_error(response, suppress)
        return response


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
