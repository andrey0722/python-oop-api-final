"""An utility which gather dog breed info and manages dog photos.

The primary (and only) function of this utility is to gather information
about all dog breeds available at https://dog.ceo/ with their variants and
also pictures of these breeds and upload them to Yandex.Disk cloud storage
(requires Yandex.Disk personal API key). After the operation is done a report
is formed and saved in JSON format to the working directory.

"""


import json
import os
import sys
from dog_ceo_api import DogCeoApi
from dotenv import load_dotenv
from yandex_disk_api import YandexDiskApi


# Default values for optional environment variables
JSON_REPORT_PATH_DEFAULT = 'report.json'
CLEAN_DEFAULT = ''
OVERWRITE_DEFAULT = ''
YD_ROOT_DIR_DEFAULT = 'disk:/dog_pictures'


class JsonReport:
    """A program report which is being formed during program operation."""

    def __init__(self):
        """Initialize a report object."""
        self._result: list[dict[str, str]] = []

    def append(self, file_name: str):
        """Append a file name to the end of the report."""
        self._result.append({'file_name': file_name})

    def save(self, file_path: str, encoding='utf-8'):
        """Save program result object as pretty-printed JSON to a file."""
        with open(file_path, 'w', encoding=encoding) as f:
            json.dump(self._result, f, indent=4)


def extract_file_name(uri: str):
    """Extract a base file name from a specified `uri`."""
    uri = uri.split('?')[0]    # Strip possible ?query component
    uri = uri.split('#')[0]    # Strip possible #fragment component
    return uri.split('/')[-1]  # Extract the last component in URI path


def get_required_env_variable(name: str) -> str:
    """Get the value of an environment variable or terminate program.

    If the environment variable exists return its value. Otherwise print
    an error message to STDERR and terminate the program with an error code.

    Args:
        name (str): Environment variable name whose value to extract.

    Returns:
        str: The value of existing environment variable.
    """
    if name not in os.environ:
        sys.stderr.write(f'ERROR: Environment variable "{name}" is '
                         f'required but not set. Please provide the '
                         f'environment variable "{name}" and try again.')
        sys.exit(1)
    return os.environ[name]


def get_optional_env_variable(var_name: str, default: str) -> str:
    """Get the value of an environment variable or use a default value.

    Args:
        var_name (str): Environment variable name whose value to extract.
        default (str): Default value to use if the variable is absent.

    Returns:
        str: The value of the environment variable or the default value.
    """
    return os.environ.get(var_name, default)


class Application:
    """A class whose instance controls the flow of the main program."""

    def __init__(self) -> None:
        """Initialize an Application instance."""

        # Override missing environment variables with .env values
        load_dotenv()

        # Get required variables
        self.yd_key = get_required_env_variable('YD_OAUTH_KEY')

        # Get optional variables
        self.report_path = get_optional_env_variable(
            'JSON_REPORT_PATH',
            JSON_REPORT_PATH_DEFAULT
        )
        self.clean = get_optional_env_variable(
            'CLEAN',
            CLEAN_DEFAULT
        )
        self.overwrite = get_optional_env_variable(
            'OVERWRITE',
            OVERWRITE_DEFAULT
        )
        self.root_dir = get_optional_env_variable(
            'YD_ROOT_DIR',
            YD_ROOT_DIR_DEFAULT
        )

        self.report = JsonReport()
        self.dog_api = DogCeoApi()
        self.yd_api = YandexDiskApi(self.yd_key)

    def process_image(self, image: str, breed: str, sub_breed: str = ''):
        """Upload an image to YD cloud storage and add to report.

        Args:
            image (str): Image URL.
            breed (str): Dog breed.
            sub_breed (str): Dog sub-breed.
        """
        image_name = extract_file_name(image)
        if sub_breed:
            file_name = f'{breed}_{sub_breed}_{image_name}'
        else:
            file_name = f'{breed}_{image_name}'
        file_path = f'{self.root_dir}/{breed}/{file_name}'
        if self.yd_api.check_item_exists(file_path):
            # When the file exists YD duplicates it with a suffix.
            # Avoid YD storage to become a trash.
            if self.overwrite:
                # Recreate the file from scratch
                self.yd_api.delete_item(file_path)
            else:
                # Skip current file
                return
        self.yd_api.upload_file_from_url(file_path, image)
        self.report.append(file_name)

    def main(self):
        """Get image URIs of all breeds and sub-breeds and save to YD storage.

        1. Extract pictures of all dog breeds and sub-breeds.
        2. Upload all pictures to YD cloud storage with grouping by breed.
        3. Create a report with uploaded image file names in JSON format.
        """
        if self.clean:
            self.yd_api.delete_item(self.root_dir)
        self.yd_api.create_directory(self.root_dir)

        breeds = self.dog_api.get_all_breeds_sub_breeds()
        for breed, sub_breeds in breeds.items():
            print(f'{breed=}')
            self.yd_api.create_directory(f'{self.root_dir}/{breed}')
            if sub_breeds:
                for sub_breed in sub_breeds:
                    images = self.dog_api.get_sub_breed_images(breed, sub_breed)
                    for image in images:
                        self.process_image(image, breed, sub_breed)
            else:
                for image in self.dog_api.get_breed_images(breed):
                    self.process_image(image, breed)

        self.report.save(self.report_path)


if __name__ == '__main__':
    app = Application()
    app.main()
