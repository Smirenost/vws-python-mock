"""
Authorization validators to use in the mock query API.
"""

from typing import Dict, List

from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._query_validators.exceptions import (
    AuthenticationFailure,
    AuthHeaderMissing,
    MalformedAuthHeader,
    QueryOutOfBounds,
)
from mock_vws.database import VuforiaDatabase


def validate_auth_header_exists(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate that there is an authorization header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if there is no "Authorization" header.
    """

    if 'Authorization' in request_headers:
        return

    raise AuthHeaderMissing


def validate_auth_header_number_of_parts(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header includes text either side of a space.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the "Authorization" header is not as
        expected.
    """

    header = request_headers['Authorization']
    parts = header.split(' ')
    if len(parts) == 2 and parts[1]:
        return

    raise MalformedAuthHeader


def validate_client_key_exists(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header includes a client key for a database.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the client key is unknown.
    """

    header = request_headers['Authorization']
    first_part, _ = header.split(':')
    _, access_key = first_part.split(' ')
    for database in databases:
        if access_key == database.client_access_key:
            return

    raise AuthenticationFailure


def validate_auth_header_has_signature(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header includes a signature.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNAUTHORIZED`` response if the "Authorization" header is not as
        expected.
    """

    header = request_headers['Authorization']
    if header.count(':') == 1 and header.split(':')[1]:
        return

    raise QueryOutOfBounds


def validate_authorization(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the authorization header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the "Authorization" header is not as
        expected.
    """

    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    if database is not None:
        return

    raise AuthenticationFailure
