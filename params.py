"""This module contains logic for extracting the program parameters."""


import os
import sys
from typing import Any, Mapping

from dotenv.main import load_dotenv

EXIT_CODE_MISSING_REQUIRED = 1
EXIT_CODE_MISSING_OPTIONAL = 2
EXIT_CODE_BAD_INTEGER = 3

class Params:
    """A class which handles extraction of the program parameters."""

    def __init__(self, defaults: Mapping[str, Any]):
        """Initialize a Params instance.

        Args:
            defaults (Mapping[str, Any]): A mapping with the default
                values for all possible parameters.
        """
        self._defaults = defaults

        # Override missing environment variables with .env values
        load_dotenv()

    def get_required_str(self, name: str) -> str:
        """Get the value of an environment variable or terminate program.

        If the environment variable exists return its value. Otherwise
        print an error message to STDERR and terminate the program with
        an error code.

        Args:
            name (str): Environment variable name whose value to extract.

        Returns:
            str: The value of existing environment variable.
        """
        return str(self._get_required(name))

    def get_optional_str(self, name: str) -> str:
        """Get the value of an environment variable or use a default value.

        The variable must contain a decimal integer value.
        If the environment variable exists return its value.
        Otherwise use the provided default value.
        If the default is missing too, print an error message
        to STDERR and terminate the program with an error code.

        Args:
            name (str): Environment variable name whose value to extract.

        Returns:
            str: The value of the environment variable or the default value.
        """
        return str(self._get_optional(name))

    def get_optional_int(self, name: str) -> int:
        """Get the value of an integer environment variable or use
        a default value.

        The variable must contain a decimal integer value.
        If the environment variable exists return its value.
        Otherwise use the provided default value.
        If the default is missing too, print an error message
        to STDERR and terminate the program with an error code.

        Args:
            name (str): Environment variable name whose value to extract.

        Returns:
            int: The value of the environment variable or the default value.
        """
        value = self._get_optional(name)
        try:
            return int(value)
        except ValueError:
            sys.stderr.write(
                f'ERROR: Environment variable "{name}" must contain '
                f'a decimal integer value but "{value}" is passed. '
                f'Please set the environment variable "{name}" to '
                f'a correct value and try again.'
            )
            sys.exit(EXIT_CODE_BAD_INTEGER)

    def _get_required(self, name: str) -> Any:
        """Internal helper to get the value of arequired parameter.

        If the environment variable exists return its value. Otherwise
        print an error message to STDERR and terminate the program with
        an error code.

        Args:
            name (str): Environment variable name whose value to extract.

        Returns:
            Any: The value of existing environment variable.
        """
        try:
            return os.environ[name]
        except KeyError:
            sys.stderr.write(
                f'ERROR: Environment variable "{name}" is required but '
                f'not set. Please provide the environment variable '
                f'"{name}" and try again.'
            )
            sys.exit(EXIT_CODE_MISSING_REQUIRED)

    def _get_optional(self, name: str) -> Any:
        """Internal helper to get the value of an optional parameter.

        If the environment variable exists return its value.
        Otherwise use the provided default value.
        If the default is missing too, print an error message
        to STDERR and terminate the program with an error code.

        Args:
            name (str): Environment variable name whose value to extract.

        Returns:
            Any: The value of the environment variable or the default value.
        """
        try:
            return os.environ[name]
        except KeyError:
            # Try the default value instead
            pass
        try:
            return self._defaults[name]
        except KeyError:
            sys.stderr.write(
                f'ERROR: Environment variable "{name}" is optional but '
                f'is somehow misses its default value. Please provide '
                f'the environment variable "{name}" and try again.'
            )
            sys.exit(EXIT_CODE_MISSING_OPTIONAL)
