"""Communication with the dog API at https://dog.ceo/api/.

This API is able to give information about known dog breeds and their local
breed variants (aka sub-breeds) and also dog pictures! The API documentation
is available at https://dog.ceo/dog-api/documentation/.

"""


import requests


class DogCeoApi:
    """A class which instance communicates with the dog API."""

    API_ROOT_DEFAULT = 'https://dog.ceo/api'

    def __init__(self, *, api_root: str = API_ROOT_DEFAULT) -> None:
        """Initialize a dog API instance.

        Args:
            api_root (str): Optional override for the API root URL.
        """
        self._api_root = api_root

    def get_all_breeds_sub_breeds(self) -> dict[str, list[str]]:
        """Return a dictionary with all available dog breeds with their
        respective sub-breeds (if any).
        """
        return self._get('breeds/list/all')

    def get_breed_images(self, breed: str) -> list[str]:
        """Return list of all image URLs for a specified breed name."""
        return self._get(f'breed/{breed}/images')

    def get_sub_breed_images(self, breed: str, sub_breed: str) -> list[str]:
        """Return list of all image URLs for a specified sub-breed name."""
        return self._get(f'breed/{breed}/{sub_breed}/images')

    def _get(self, endpoint: str):
        """Internal helper to perform a GET request to an API `endpoint`.

        Args:
            endpoint (str): The path relative to the API root URL.

        Returns:
            Any: The `message` field extracted from the JSON response body.
        """
        uri = f'{self._api_root}/{endpoint}'
        response = requests.get(uri)
        response.raise_for_status()
        root_json = response.json()
        return root_json['message']
