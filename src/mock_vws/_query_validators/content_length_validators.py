"""
Content-Length header validators to use in the mock.
"""

import uuid
from typing import Dict, List

import wrapt
from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase

from .._mock_common import json_dump
from mock_vws._query_validators.exceptions import ContentLengthHeaderNotInt, ContentLengthHeaderTooLarge, AuthenticationFailureGoodFormatting


def validate_content_length_header_is_int(
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
    given_content_length = request_headers['Content-Length']

    try:
        int(given_content_length)
    except ValueError:
        raise ContentLengthHeaderNotInt



def validate_content_length_header_not_too_large(
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
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)
    if given_content_length_value > body_length:
        raise ContentLengthHeaderTooLarge



def validate_content_length_header_not_too_small(
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
    given_content_length = request_headers['Content-Length']

    body_length = len(request_body if request_body else b'')
    given_content_length_value = int(given_content_length)

    if given_content_length_value < body_length:
        raise AuthenticationFailureGoodFormatting
