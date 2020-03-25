"""
Content-Length header validators to use in the mock.
"""

from typing import Dict, List

from mock_vws._services_validators.exceptions import (
    AuthenticationFailure,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
)
from mock_vws.database import VuforiaDatabase


def validate_content_length_header_is_int(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is an integer.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if the content length header is not an
        integer.
    """
    body_length = len(request_body if request_body else b'')
    given_content_length = request_headers.get('Content-Length', body_length)

    try:
        int(given_content_length)
    except ValueError:
        raise ContentLengthHeaderNotInt


def validate_content_length_header_not_too_large(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is not too large.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``GATEWAY_TIMEOUT`` response if the given content length header says
        that the content length is greater than the body length.
    """
    body_length = len(request_body if request_body else b'')
    given_content_length = request_headers.get('Content-Length', body_length)
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        raise ContentLengthHeaderTooLarge


def validate_content_length_header_not_too_small(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the ``Content-Length`` header is not too small.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the given content length header says
        that the content length is smaller than the body length.
    """
    body_length = len(request_body if request_body else b'')
    given_content_length = request_headers.get('Content-Length', body_length)
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        raise AuthenticationFailure
