"""
Validators for the ``Accept`` header.
"""

from typing import Dict, List

import wrapt
from requests import codes

from mock_vws.database import VuforiaDatabase

from mock_vws._query_validators.exceptions import InvalidAcceptHeader

@wrapt.decorator
def validate_accept_header(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the accept header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `NOT_ACCEPTABLE` response if the Accept header is given and is not
        'application/json' or '*/*'.
    """
    accept = request_headers.get('Accept')
    if accept in ('application/json', '*/*', None):
        return

    raise InvalidAcceptHeader
    context.headers.pop('Content-Type')
    context.status_code = codes.NOT_ACCEPTABLE
    return ''
