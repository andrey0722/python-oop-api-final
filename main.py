"""An utility which gather dog breed info and manages dog photos.

The primary (and only) function of this utility is to gather information
about all dog breeds available at https://dog.ceo/ with their variants and
also pictures of these breeds and upload them to Yandex.Disk cloud storage
(requires Yandex.Disk personal API key). After the operation is done a report
is formed and saved in JSON format to the working directory.

"""


import json
import threading
import time

from tqdm import tqdm

from params import Params
from dog_ceo_api import DogCeoApi
from utils import StagedTqdm
from web_api import extract_base_name
from yandex_disk_api import YandexDiskApi, YandexDiskApiDummy


# Default values for optional parameters
# See .env.example file for variable description.
DEFAULT_PARAMS = {
    'JSON_REPORT_PATH': 'report.json',
    'CLEAN': '',
    'OVERWRITE': '',
    'USE_RECYCLE_BIN': 'Y',
    'MAX_BREED_IMAGE_COUNT': 1,
    'MAX_SUB_BREED_IMAGE_COUNT': 1,
    'YD_ROOT_DIR': 'disk:/dog_pictures',
    'YD_TEST_DUMMY': '',
}


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


class Application:
    """A class whose instance controls the flow of the main program."""

    def __init__(self) -> None:
        """Initialize an Application instance."""
        self.params = Params(DEFAULT_PARAMS)

        # Get required parameters
        self.yd_key = self.params.get_required_str('YD_OAUTH_KEY')

        # Get optional parameters
        self.report_path = self.params.get_optional_str('JSON_REPORT_PATH')
        self.clean = self.params.get_optional_str('CLEAN')
        self.overwrite = self.params.get_optional_str('OVERWRITE')
        self.use_recycle_bin = self.params.get_optional_str('USE_RECYCLE_BIN')
        self.root_dir = self.params.get_optional_str('YD_ROOT_DIR')
        self.yd_test_dummy = self.params.get_optional_str('YD_TEST_DUMMY')
        self.max_breed_images = self.params.get_optional_int(
            'MAX_BREED_IMAGE_COUNT'
        )
        self.max_sub_breed_images = self.params.get_optional_int(
            'MAX_SUB_BREED_IMAGE_COUNT'
        )

        self.report = JsonReport()
        self.dog_api = DogCeoApi()
        self.yd_api = self.create_yd_api(bool(self.yd_test_dummy))

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

    def delete_root_directory(self):
        """Delete root directory with progress tracking."""

        # This operation may take a long while
        # if the root drectory is big, so use a thread
        def thread_action():
            """Delete root directory in a thread."""
            permanently = not self.use_recycle_bin
            self.yd_api.delete_item(self.root_dir, permanently=permanently)

        # Track progress while the thread is running
        progress = tqdm(
            bar_format=(
                'Deleting root directory, this might take a while...'
                ' [{elapsed}{postfix}]'
            )
        )
        with progress:
            thread = threading.Thread(target=thread_action)
            thread.start()
            while thread.is_alive():
                progress.update()
                time.sleep(1)
            thread.join()

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
                self.delete_root_directory()
            self.yd_api.create_directory(self.root_dir)

            breeds = self.dog_api.get_all_breeds_sub_breeds()

            # Minimal width of the progress bars description field
            desc_width = 25

            # Progress over all breeds (total program progress)
            total_progress = StagedTqdm(
                desc=f'{'Total':{desc_width}}',
                substage_units='breeds'
            )

            # Progress over current breed (sub-breed/images or images)
            breed_progress = StagedTqdm(
                stage_units='sub-breeds',
                substage_units='images'
            )

            with total_progress, breed_progress:
                total_progress.reset_substage(len(breeds))

                # Process all breeds
                for breed, sub_breeds in breeds.items():
                    self.yd_api.create_directory(f'{self.root_dir}/{breed}')

                    breed_progress.reset_stage(len(sub_breeds))

                    if sub_breeds:
                        # Process all breed sub-breeds
                        for sub_breed in sub_breeds:
                            images = self.dog_api.get_sub_breed_random_images(
                                breed,
                                sub_breed,
                                self.max_sub_breed_images
                            )
                            breed_progress.set_description(
                                f'{f'{breed}-{sub_breed}':{desc_width}}'
                            )
                            breed_progress.reset_substage(len(images))
                            # Process sub-breed images
                            for image in images:
                                self.process_image(image, breed, sub_breed)
                                breed_progress.update_substage()
                            breed_progress.update_stage()
                    else:
                        # No sub-breed, upload images just for the breed
                        images = self.dog_api.get_breed_random_images(
                            breed,
                            self.max_breed_images
                        )
                        breed_progress.set_description(f'{breed:{desc_width}}')
                        breed_progress.reset_substage(len(images))

                        # Process breed images
                        for image in images:
                            self.process_image(image, breed)
                            breed_progress.update_substage()
                    total_progress.update_substage()
        finally:
            self.report.save(self.report_path)


if __name__ == '__main__':
    with Application() as app:
        app.main()
