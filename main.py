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


class BreedTqdm(tqdm):
    """A class for progress tracking while processing single dog breed."""

    def __init__(
        self,
        *args,
        image: int = 0,
        total_images: int = 0,
        sub_breed: int = 0,
        total_sub_breeds: int = 0,
        **kwargs
    ):
        """Intialize a progress bar instance.

        Args:
            image (int): Current image index.
            total_images (int): Total number of images.
            sub_breed (int): Current sub-breed index.
            total_sub_breeds (int): Total number of images.
        """
        # Define custom properties before superclass __init__
        self.image = image
        self.total_images = total_images
        self.sub_breed = sub_breed
        self.total_sub_breeds = total_sub_breeds

        super().__init__(*args, **kwargs)

        # Override progress bar format
        # Replace the {n_fmt}/{total_fmt} part with custom format
        self.bar_format = (
            '{l_bar}{bar}| {breed_stats} '
            '[{elapsed}<{remaining}, {rate_fmt}{postfix}]'
        )

    @property
    def format_dict(self):
        """Add custom properties for the progress formatter."""
        d = super().format_dict

        # Calculate current progress position
        d['n'] = self._calc_n()
        d['total'] = self._calc_total()

        # Pre-format the breed stats
        breed_stats = []
        if self.total_sub_breeds:
            # Don't track current sub-breed if they are absent
            breed_stats.append(
                f'{self.sub_breed}/{self.total_sub_breeds} sub-breeds'
            )
        # Track current image count
        breed_stats.append(
            f'{self.image}/{self.total_images} images'
        )
        d['breed_stats'] = ', '.join(breed_stats)

        return d

    def reset_image(self, total_images: int | None = None):
        """Resets image position to 0 for repeated use.

        Args:
            total_images (int | None): Optional value to update
                `total_images` property. If None, then `total_images`
                remain unchanged.
        """
        self.image = 0
        if total_images is not None:
            self.total_images = total_images
        self.initial = self._calc_n()
        self.reset(self._calc_total())

    def update_image(self, diff_image: int = 1):
        """Manually update the image progress.

        Args:
            diff_image (int): Current image position increment.
        """
        self.image += diff_image
        self.update(0)

    def reset_sub_breed(self, total_sub_breeds: int | None = None):
        """Resets sub-breed position to 0 for repeated use.

        Args:
            total_sub_breeds (int | None): Optional value to update
                `total_sub_breeds` property. If None, then
                `total_sub_breeds` remain unchanged.
        """
        self.sub_breed = 0
        if total_sub_breeds is not None:
            self.total_sub_breeds = total_sub_breeds
        self.initial = self._calc_n()
        self.reset(self._calc_total())

    def update_sub_breed(self, diff_sub_breed: int = 1):
        """Manually update the sub-breed progress.

        Args:
            diff_sub_breed (int): Current sub-breed position increment.
        """
        self.sub_breed += diff_sub_breed
        self.update(0)

    def _calc_n(self):
        """Internal helper to calculate current progress position."""
        if self.total_sub_breeds:
            return self.sub_breed * self.total_images + self.image
        return self.image

    def _calc_total(self):
        """Internal helper to calculate progress total count."""
        if self.total_sub_breeds:
            return self.total_sub_breeds * self.total_images
        return self.total_images


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

            desc_width = 25
            with tqdm() as total_progress, BreedTqdm() as breed_progress:
                # Progress over all breeds (total program progress)
                total_progress.set_description(f'{'Total':{desc_width}}')
                total_progress.reset(len(breeds))

                # Process all breeds
                for breed, sub_breeds in breeds.items():
                    self.yd_api.create_directory(f'{self.root_dir}/{breed}')

                    # Progress over current breed
                    breed_progress.reset_sub_breed(len(sub_breeds))

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
                            breed_progress.reset_image(len(images))
                            # Process sub-breed images
                            for image in images:
                                self.process_image(image, breed, sub_breed)
                                breed_progress.update_image()
                            breed_progress.update_sub_breed()
                    else:
                        # No sub-breed, upload images just for the breed
                        images = self.dog_api.get_breed_random_images(
                            breed,
                            self.max_breed_images
                        )
                        breed_progress.set_description(f'{breed:{desc_width}}')
                        breed_progress.reset_image(len(images))

                        # Process breed images
                        for image in images:
                            self.process_image(image, breed)
                            breed_progress.update_image()
                    total_progress.update()
        finally:
            self.report.save(self.report_path)


if __name__ == '__main__':
    with Application() as app:
        app.main()
