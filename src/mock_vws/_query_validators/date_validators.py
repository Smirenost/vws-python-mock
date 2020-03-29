"""
Validators of the date header to use in the mock query API.
"""

import datetime
import uuid
from typing import Any, Callable, Dict, Set, List, Tuple

import pytz
import wrapt
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from .._mock_common import json_dump
from mock_vws._query_validators.exceptions import DateHeaderNotGiven, DateFormatNotValid, RequestTimeTooSkewed


@wrapt.decorator
def validate_date_header_given(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the date header is given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the date is not given.
    """
    if 'Date' in request_headers:
        return

    raise DateHeaderNotGiven

def _accepted_date_formats() -> Set[str]:
    """
    Return all known accepted date formats.

    We expect that more formats than this will be accepted.
    These are the accepted ones we know of at the time of writing.
    """
    known_accepted_formats = {
        '%a, %b %d %H:%M:%S %Y',
        '%a %b %d %H:%M:%S %Y',
        '%a, %d %b %Y %H:%M:%S',
        '%a %d %b %Y %H:%M:%S',
    }

    known_accepted_formats = known_accepted_formats.union(
        set(date_format + ' GMT' for date_format in known_accepted_formats),
    )

    return known_accepted_formats


@wrapt.decorator
def validate_date_format(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the format of the date header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNAUTHORIZED` response if the date is in the wrong format.
    """
    date_header = request_headers['Date']

    for date_format in _accepted_date_formats():
        try:
            datetime.datetime.strptime(date_header, date_format)
        except ValueError:
            pass
        else:
            return

    raise DateFormatNotValid


@wrapt.decorator
def validate_date_in_range(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate date in the date header given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response if the date is out of range.
    """
    date_header = request_headers['Date']

    for date_format in _accepted_date_formats():
        try:
            date = datetime.datetime.strptime(date_header, date_format)
            # We could break here but that would give a coverage report that is
            # not 100%.
        except ValueError:
            pass

    gmt = pytz.timezone('GMT')
    now = datetime.datetime.now(tz=gmt)
    date_from_header = date.replace(tzinfo=gmt)
    time_difference = now - date_from_header

    maximum_time_difference = datetime.timedelta(minutes=65)

    if abs(time_difference) < maximum_time_difference:
        return

    raise RequestTimeTooSkewed
