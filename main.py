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

from pydantic_settings import BaseSettings, SettingsConfigDict
from tqdm import tqdm

from dog_ceo_api import DogCeoApi
from utils import StagedTqdm
from web_api import extract_base_name
from yandex_disk_api import YandexDiskApi, YandexDiskApiDummy


class Settings(BaseSettings):
    """Project external parameters loaded from the environment.

    See .env.example file for variable description.
    """

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # Required parameters
    yd_oauth_key: str

    # Optional parameters
    report_path: str = 'report.json'
    clean: bool = False
    overwrite: bool = False
    use_recycle_bin: bool = True
    max_breed_images: int = 1
    max_sub_breed_images: int = 1
    yd_root_dir: str = 'disk:/dog_pictures'
    yd_test_dummy: bool = False


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
        self.settings = Settings()  # type: ignore[reportCallIssue]
        self.report = JsonReport()
        self.dog_api = DogCeoApi()
        self.yd_api = self.create_yd_api()

        # Minimal width of the progress bars description field
        self.desc_width = 25

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

    def create_yd_api(self) -> YandexDiskApi:
        """Create and return YD API instance."""
        if self.settings.yd_test_dummy:
            return YandexDiskApiDummy(self.settings.yd_oauth_key)
        return YandexDiskApi(self.settings.yd_oauth_key)

    def delete_root_directory(self):
        """Delete root directory with progress tracking."""

        # This operation may take a long while
        # if the root drectory is big, so use a thread
        def thread_action():
            """Delete root directory in a thread."""
            self.yd_api.delete_item(
                self.settings.yd_root_dir,
                permanently=not self.settings.use_recycle_bin,
            )

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

    def process_image(
        self,
        image: str,
        breed: str,
        sub_breed: str | None = None,
    ):
        """Upload an image to YD cloud storage and add to report.

        Args:
            image (str): Image URL.
            breed (str): Dog breed.
            sub_breed (str | None): Dog sub-breed. If None then use
                the breed without sub-breed.
        """
        image_name = extract_base_name(image)
        sub_breed_str = f'_{sub_breed}' if sub_breed else ''
        file_name = f'{breed}{sub_breed_str}_{image_name}'
        file_path = f'{self.settings.yd_root_dir}/{breed}/{file_name}'
        if self.settings.overwrite:
            # Recreate the file from scratch regardless if it exists
            self.yd_api.delete_item(
                file_path,
                permanently=not self.settings.use_recycle_bin,
                ignore_non_existent=True,
            )
        elif self.yd_api.check_item_exists(file_path):
            # When the file exists YD duplicates it with a suffix.
            # Avoid YD storage to become a trash - skip current file.
            return
        self.yd_api.upload_file_from_url(file_path, image)
        self.report.append(file_name)

    def process_sub_breed(
        self,
        breed: str,
        sub_breed: str | None,
        progress: StagedTqdm,
    ):
        """Process images of an entire dog sub-breed (if any).

        Args:
            breed (str): Dog breed.
            sub_breed (str | None): Dog sub-breed. If None then use
                the breed without sub-breed.
            progress (StagedTqdm): Breed progress.
        """
        if sub_breed:
            count = self.settings.max_sub_breed_images
        else:
            count = self.settings.max_breed_images
        images = self.dog_api.get_breed_random_images(count, breed, sub_breed)
        sub_breed_str = f'-{sub_breed}' if sub_breed else ''
        progress.set_description(self.format_desc(f'{breed}{sub_breed_str}'))
        progress.reset_substage(len(images))
        for image in images:
            self.process_image(image, breed, sub_breed)
            progress.update_substage()
        progress.update_stage()

    def process_breed(
        self,
        breed: str,
        sub_breeds: list[str],
        progress: StagedTqdm,
    ):
        """Process images of an entire dog breed.

        Args:
            breed (str): Dog breed.
            sub_breeds (list[str]): Dog sub-breeds.
            progress (StagedTqdm): Breed progress.
        """
        progress.reset_stage(len(sub_breeds))
        if sub_breeds:
            # Process all breed sub-breeds
            for sub_breed in sub_breeds:
                self.process_sub_breed(breed, sub_breed, progress)
        else:
            # No sub-breed, upload images just for the breed
            self.process_sub_breed(breed, None, progress)

    def format_desc(self, text: str) -> str:
        """Format description string using minimum width.

        Args:
            text (str): Description text to format.

        Returns:
            str: Formatted descriotion text.
        """
        return f'{text:{self.desc_width}}'

    def main(self):
        """Get image URIs of all breeds and sub-breeds and save to YD storage.

        1. Extract pictures of all dog breeds and sub-breeds.
        2. Upload all pictures to YD cloud storage with grouping by breed.
        3. Create a report with uploaded image file names in JSON format.
        """
        try:
            if self.settings.clean:
                self.delete_root_directory()
            self.yd_api.create_directory(self.settings.yd_root_dir)

            breeds = self.dog_api.get_all_breeds_sub_breeds()

            # Progress over all breeds (total program progress)
            total_progress = StagedTqdm(
                desc=self.format_desc('Total'),
                substage_units='breeds',
                disable=True,
            )

            # Progress over current breed (sub-breed/images or images)
            breed_progress = StagedTqdm(
                stage_units='sub-breeds',
                substage_units='images',
                disable=True,
            )

            with total_progress, breed_progress:
                total_progress.reset_substage(len(breeds))

                # Process all breeds
                for breed, sub_breeds in breeds.items():
                    self.yd_api.create_directory(
                        f'{self.settings.yd_root_dir}/{breed}'
                    )
                    self.process_breed(breed, sub_breeds, breed_progress)
                    total_progress.update_substage()
        finally:
            self.report.save(self.settings.report_path)


if __name__ == '__main__':
    with Application() as app:
        app.main()
