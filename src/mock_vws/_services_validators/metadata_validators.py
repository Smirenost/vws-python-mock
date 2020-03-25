"""
Validators for application metadata.
"""

import binascii
import json

from requests import codes

from mock_vws._base64_decoding import decode_base64
from mock_vws._services_validators.exceptions import Fail, MetadataTooLarge


def validate_metadata_size(request_text: str, ) -> None:
    """
    Validate that the given application metadata is a string or 1024 * 1024
    bytes or fewer.

    Args:
        request_text: The content of the request.

    Raises:
        MetadataTooLarge: Application metadata is given and it is too large.
    """
    if not request_text:
        return

    request_json = json.loads(request_text)
    application_metadata = request_json.get('application_metadata')
    if application_metadata is None:
        return
    decoded = decode_base64(encoded_data=application_metadata)

    max_metadata_bytes = 1024 * 1024 - 1
    if len(decoded) <= max_metadata_bytes:
        return

    raise MetadataTooLarge


def validate_metadata_encoding(request_text: str, ) -> None:
    """
    Validate that the given application metadata can be base64 decoded.

    Args:
        request_text: The content of the request.

    Raises:
        Fail: Application metadata is given and it cannot be base64
            decoded.
    """
    if not request_text:
        return

    request_json = json.loads(request_text)
    if 'application_metadata' not in request_json:
        return

    application_metadata = request_json.get('application_metadata')

    if application_metadata is None:
        return

    try:
        decode_base64(encoded_data=application_metadata)
    except binascii.Error:
        raise Fail(status_code=codes.UNPROCESSABLE_ENTITY)


def validate_metadata_type(request_text: str, ) -> None:
    """
    Validate that the given application metadata is a string or NULL.

    Args:
        request_text: The content of the request.

    Raises:
        Fail: Application metadata is given and it is not a string or NULL.
    """
    if not request_text:
        return

    request_json = json.loads(request_text)
    if 'application_metadata' not in request_json:
        return

    application_metadata = request_json.get('application_metadata')

    if application_metadata is None or isinstance(application_metadata, str):
        return

    raise Fail(status_code=codes.BAD_REQUEST)
