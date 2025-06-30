"""An utility which gather dog breed info and manages dog photos.

The primary (and only) function of this utility is to gather information
about all dog breeds available at https://dog.ceo/ with their variants and
also pictures of these breeds and upload them to Yandex.Disk cloud storage
(requires Yandex.Disk personal API key). After the operation is done a report
is formed and saved in JSON format to the working directory.

"""


import json
from dog_ceo_api import DogCeoApi


RESULT_FILE_PATH = 'result.json'


class Report:
    """A program report which is being formed during program operation."""

    def __init__(self):
        """Initialize a report object."""
        self._result: list[dict[str, str]] = []

    def append(self, file_name: str):
        """Append a file name to the end of the report."""
        self._result.append({'file_name': file_name})

    def save(self, file_path=RESULT_FILE_PATH, encoding='utf-8'):
        """Save program result object as pretty-printed JSON to a file."""
        with open(file_path, 'w', encoding=encoding) as f:
            json.dump(self._result, f, indent=4)


def extract_file_name(uri: str):
    """Extract a base file name from a specified `uri`."""
    uri = uri.split('?')[0]    # Strip possible ?query component
    uri = uri.split('#')[0]    # Strip possible #fragment component
    return uri.split('/')[-1]  # Extract the last component in URI path


def main():
    """Get image URIs of all breeds and sub-breeds. Save all image
    file names in a JSON report.
    """
    report = Report()
    dog_api = DogCeoApi()
    breeds = dog_api.get_all_breeds_sub_breeds()
    for breed, sub_breeds in breeds.items():
        print(f'{breed=}')
        if sub_breeds:
            for sub_breed in sub_breeds:
                for image in dog_api.get_sub_breed_images(breed, sub_breed):
                    image_name = extract_file_name(image)
                    file_name = f'{breed}_{sub_breed}_{image_name}'
                    report.append(file_name)
        else:
            for image in dog_api.get_breed_images(breed):
                image_name = extract_file_name(image)
                file_name = f'{breed}_{image_name}'
                report.append(file_name)
    report.save()


if __name__ == '__main__':
    main()
