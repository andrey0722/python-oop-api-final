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

from dotenv import load_dotenv
from tqdm import tqdm

from dog_ceo_api import DogCeoApi
from web_api import extract_base_name
from yandex_disk_api import YandexDiskApi, YandexDiskApiDummy


# Default values for optional environment variables
# See .env.example file for variable description.
JSON_REPORT_PATH_DEFAULT = 'report.json'
CLEAN_DEFAULT = ''
OVERWRITE_DEFAULT = ''
USE_RECYCLE_BIN_DEFAULT = 'Y'
YD_ROOT_DIR_DEFAULT = 'disk:/dog_pictures'
MAX_BREED_IMAGE_COUNT_DEFAULT = 10
MAX_SUB_BREED_IMAGE_COUNT_DEFAULT = 1


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


def get_optional_env_variable(name: str, default: str) -> str:
    """Get the value of an environment variable or use a default value.

    Args:
        name (str): Environment variable name whose value to extract.
        default (str): Default value to use if the variable is absent.

    Returns:
        str: The value of the environment variable or the default value.
    """
    return os.environ.get(name, default)


def get_optional_env_variable_int(name: str, default: int) -> int:
    """Get the value of an integer environment variable or use
    a default value. The variable must contain a decimal integer value.

    Args:
        name (str): Environment variable name whose value to extract.
        default (int): Default value to use if the variable is absent.

    Returns:
        int: The value of the environment variable or the default value.
    """
    value = os.environ.get(name, default)
    try:
        return int(value)
    except ValueError:
        sys.stderr.write(f'WARNING: Environment variable "{name}" must '
                         f'contain a decimal integer value but "{value}" '
                         f'is passed. Please set the environment variable '
                         f'"{name}" to a correct value and try again.')
        return default


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
        self.use_recycle_bin = get_optional_env_variable(
            'USE_RECYCLE_BIN',
            USE_RECYCLE_BIN_DEFAULT
        )
        self.root_dir = get_optional_env_variable(
            'YD_ROOT_DIR',
            YD_ROOT_DIR_DEFAULT
        )
        self.max_breed_images = get_optional_env_variable_int(
            'MAX_BREED_IMAGE_COUNT',
            MAX_BREED_IMAGE_COUNT_DEFAULT
        )
        self.max_sub_breed_images = get_optional_env_variable_int(
            'MAX_SUB_BREED_IMAGE_COUNT',
            MAX_SUB_BREED_IMAGE_COUNT_DEFAULT
        )

        self.report = JsonReport()
        self.dog_api = DogCeoApi()
        self.yd_api = self.create_yd_api()

    def __enter__(self):
        """Do nothing."""
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Close all API connections."""
        self.close()

    def close(self):
        """Close all API connections."""
        self.dog_api.close()
        self.yd_api.close()

    def create_yd_api(self, test: bool = False) -> YandexDiskApi:
        """Create and return YD API instance.

        Args:
            test (bool): If True create test implementation. If False
                create real implementation
        """
        if test:
            return YandexDiskApiDummy(self.yd_key)
        return YandexDiskApi(self.yd_key)

    def process_image(self, image: str, breed: str, sub_breed: str = ''):
        """Upload an image to YD cloud storage and add to report.

        Args:
            image (str): Image URL.
            breed (str): Dog breed.
            sub_breed (str): Dog sub-breed.
        """
        image_name = extract_base_name(image)
        if sub_breed:
            file_name = f'{breed}_{sub_breed}_{image_name}'
        else:
            file_name = f'{breed}_{image_name}'
        file_path = f'{self.root_dir}/{breed}/{file_name}'
        if self.overwrite:
            # Recreate the file from scratch regardless if it exists
            permanently = not self.use_recycle_bin
            self.yd_api.delete_item(
                file_path,
                permanently=permanently,
                ignore_non_existent=True
            )
        elif self.yd_api.check_item_exists(file_path):
            # When the file exists YD duplicates it with a suffix.
            # Avoid YD storage to become a trash - skip current file.
            return
        self.yd_api.upload_file_from_url(file_path, image)
        self.report.append(file_name)

    def main(self):
        """Get image URIs of all breeds and sub-breeds and save to YD storage.

        1. Extract pictures of all dog breeds and sub-breeds.
        2. Upload all pictures to YD cloud storage with grouping by breed.
        3. Create a report with uploaded image file names in JSON format.
        """
        try:
            if self.clean:
                permanently = not self.use_recycle_bin
                self.yd_api.delete_item(self.root_dir, permanently=permanently)
            self.yd_api.create_directory(self.root_dir)

            breeds = self.dog_api.get_all_breeds_sub_breeds()

            desc_width = 17
            with tqdm() as total_progress, tqdm() as breed_progress:
                # Progress over all breeds (total program progress)
                total_progress.set_description(f'{'Total':{desc_width}}')
                total_progress.reset(len(breeds))

                # Process all breeds
                for breed, sub_breeds in breeds.items():
                    self.yd_api.create_directory(f'{self.root_dir}/{breed}')

                    # Progress over current breed
                    breed_progress.set_description(f'{breed:{desc_width}}')

                    if sub_breeds:
                        # Process all breed sub-breeds
                        limit = self.max_sub_breed_images * len(sub_breeds)
                        breed_progress.reset(limit)
                        for sub_breed in sub_breeds:
                            images = self.dog_api.get_sub_breed_random_images(
                                breed,
                                sub_breed,
                                self.max_sub_breed_images
                            )
                            # Process sub-breed images
                            for image in images:
                                self.process_image(image, breed, sub_breed)
                                breed_progress.update(1)
                    else:
                        # No sub-breed, upload images just for the breed
                        images = self.dog_api.get_breed_random_images(
                            breed,
                            self.max_breed_images
                        )
                        breed_progress.reset(len(images))

                        # Process breed images
                        for image in images:
                            self.process_image(image, breed)
                            breed_progress.update(1)
                    total_progress.update(1)
        finally:
            self.report.save(self.report_path)


if __name__ == '__main__':
    with Application() as app:
        app.main()
