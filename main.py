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


def save_result(result, file_path=RESULT_FILE_PATH, encoding='utf-8'):
    """Save program result object as pretty-printed JSON to a file."""
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(result, f, indent=4)


def main():
    """List all breeds and subbreeds from the dog API."""
    result: list[dict[str, str]] = []
    dog_api = DogCeoApi()
    breeds = dog_api.get_all_breeds_subbreeds()
    for breed, subbreeds in breeds.items():
        print(f'{breed=}')
        result.append({'breed': breed})
        for subbreed in subbreeds:
            print(f'    {subbreed=}')
            result.append({'subbreed': f'{breed}-{subbreed}'})
    save_result(result)


if __name__ == '__main__':
    main()
