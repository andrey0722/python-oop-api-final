"""Communication with the dog API at https://dog.ceo/api/.

This API is able to give information about known dog breeds and their local
breed variants (aka sub-breeds) and also dog pictures! The API documentation
is available at https://dog.ceo/dog-api/documentation/.

"""


from web_api import BasicWebApi


class DogCeoApi(BasicWebApi):
    """A class which instance communicates with the dog API."""

    API_ROOT_DEFAULT = 'https://dog.ceo/api'

    # This API sometimes take a long time to respond
    REQUEST_TIMEOUT = (21.05, 40.0)

    def __init__(self, *, api_root: str = API_ROOT_DEFAULT):
        """Initialize a dog API instance.

        Args:
            api_root (str): Optional override for the API root URL.
        """
        request_timeout = type(self).REQUEST_TIMEOUT
        super().__init__(api_root=api_root, request_timeout=request_timeout)

    def get_all_breeds_sub_breeds(self) -> dict[str, list[str]]:
        """Return a dictionary with all available dog breeds with their
        respective sub-breeds (if any).
        """
        return self._get('breeds/list/all')

    def get_breed_images(
        self,
        breed: str,
        sub_breed: str | None = None,
    ) -> list[str]:
        """Return list of all image URLs for a specified sub-breed name.

        Args:
            breed (str): Dog breed name.
            sub_breed (str | None): Dog sub-breed name. If None or empty
                string then use just the breed with no sub-breed.
        """
        sub_breed_str = f'/{sub_breed}' if sub_breed else ''
        return self._get(f'breed/{breed}{sub_breed_str}/images')

    def get_breed_random_image(
        self,
        breed: str,
        sub_breed: str | None = None,
    ) -> str:
        """Return a random image URL for a specified sub-breed name.

        Args:
            breed (str): Dog breed name.
            sub_breed (str | None): Dog sub-breed name. If None or empty
                string then use just the breed with no sub-breed.
        """
        sub_breed_str = f'/{sub_breed}' if sub_breed else ''
        return self._get(f'breed/{breed}{sub_breed_str}/images/random')

    def get_breed_random_images(
        self,
        count: int,
        breed: str,
        sub_breed: str | None = None,
    ) -> list[str]:
        """Return list of random image URLs for a specified sub-breed name.

        Args:
            count (int): Maximum image count to return.
            breed (str): Dog breed name.
            sub_breed (str | None): Dog sub-breed name. If None or empty
                string then use just the breed with no sub-breed.
        """
        sub_breed_str = f'/{sub_breed}' if sub_breed else ''
        return self._get(f'breed/{breed}{sub_breed_str}/images/random/{count}')

    def _get(self, endpoint: str):
        """Internal helper to perform a GET request to an API endpoint.

        Args:
            endpoint (str): The path relative to the API root URL.

        Returns:
            Any: The `message` field extracted from the JSON response body.
        """
        response = self._request('GET', endpoint)
        root_json = response.json()
        return root_json['message']
