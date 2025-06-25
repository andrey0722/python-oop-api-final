"""Communication with the dog API at https://dog.ceo/api/.

This API is able to give information about known dog breeds and their local
breed variants (aka sub-breeds) and also dog pictures! The API documentation
is available at https://dog.ceo/dog-api/documentation/.

"""


import requests


class DogCeoApi:
    """A class which instance communicates with the dog API."""

    def __init__(self) -> None:
        """Initialize a dog API instance."""
        pass

    def get_all_breeds_subbreeds(self) -> dict[str, list[str]]:
        """Return a dictionary with all available dog breeds with their
        respective subbreeds (if any).

        """
        response = requests.get('https://dog.ceo/api/breeds/list/all')
        response.raise_for_status()
        result_root = response.json()
        return result_root['message']
