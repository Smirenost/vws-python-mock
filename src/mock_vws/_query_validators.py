"""
Input validators to use in the mock query API.
"""

import cgi
import datetime
import io
import uuid
from typing import Any, Callable, Dict, Set, Tuple

import pytz
import requests
import wrapt
from PIL import Image
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes, States
from mock_vws._mock_common import (
    authorization_header,
    json_dump,
    parse_multipart,
)


@wrapt.decorator
def validate_auth_header_exists(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args
    if 'Authorization' in request.headers:
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    text = 'Authorization header missing.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text


@wrapt.decorator
def validate_authorization(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    content_type = request.headers.get('Content-Type', '').split(';')[0]
    expected_authorization_header = authorization_header(
        access_key=instance.access_key,
        secret_key=instance.secret_key,
        method=request.method,
        content=request.body or b'',
        content_type=content_type,
        date=request.headers.get('Date', ''),
        request_path=request.path,
    )

    if request.headers['Authorization'] == expected_authorization_header:
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    text = 'Malformed authorization header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    context.headers['WWW-Authenticate'] = 'VWS'
    return text


@wrapt.decorator
def validate_project_state(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the state of the project.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `FORBIDDEN` response with an InactiveProject result code if the
        project is inactive.
    """
    _, context = args

    if instance.database.state != States.PROJECT_INACTIVE:
        return wrapped(*args, **kwargs)

    context.status_code = codes.FORBIDDEN
    transaction_id = uuid.uuid4().hex
    result_code = ResultCodes.INACTIVE_PROJECT.value

    # The response has an unusual format of separators, so we construct it
    # manually.
    return (
        '{"transaction_id": '
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        '}'
    )


@wrapt.decorator
def validate_image_file_size(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the file size of the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.

    Raises:
        requests.exceptions.ConnectionError: The image file size is too large.
    """
    request, _ = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    # This is the documented maximum size of a PNG as per.
    # https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
    # However, the tests show that this maximum size also applies to JPEG
    # files.
    max_bytes = 2 * 1024 * 1024
    if len(image) > max_bytes:
        raise requests.exceptions.ConnectionError
    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_image_format(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the format of the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        either a PNG or a JPEG.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    assert isinstance(image, bytes)
    image_file = io.BytesIO(image)
    pil_image = Image.open(image_file)

    if pil_image.format in ('PNG', 'JPEG'):
        return wrapped(*args, **kwargs)

    context.status_code = codes.UNPROCESSABLE_ENTITY
    transaction_id = uuid.uuid4().hex
    result_code = ResultCodes.BAD_IMAGE.value

    # The response has an unusual format of separators, so we construct it
    # manually.
    return (
        '{"transaction_id": '
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        '}'
    )


@wrapt.decorator
def validate_image_file_contents(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the format of the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        either a PNG or a JPEG.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    assert isinstance(image, bytes)
    image_file = io.BytesIO(image)

    try:
        Image.open(image_file).verify()
    except SyntaxError:
        context.status_code = codes.UNPROCESSABLE_ENTITY
        transaction_id = uuid.uuid4().hex
        result_code = ResultCodes.BAD_IMAGE.value

        # The response has an unusual format of separators, so we construct it
        # manually.
        return (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_date_header_given(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    if 'Date' in request.headers:
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    return 'Date header required.'


@wrapt.decorator
def validate_max_num_results(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``max_num_results`` field is either an integer within range or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``max_num_results`` field is either not
        an integer, or an integer out of range.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )
    [max_num_results] = parsed.get('max_num_results', ['1'])
    invalid_type_error = (
        f"Invalid value '{max_num_results}' in form data part "
        "'max_result'. "
        'Expecting integer value in range from 1 to 50 (inclusive).'
    )

    try:
        max_num_results_int = int(max_num_results)
    except ValueError:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    java_max_int = 2147483647
    if max_num_results_int > java_max_int:
        context.status_code = codes.BAD_REQUEST
        return invalid_type_error

    if max_num_results_int < 1 or max_num_results_int > 50:
        context.status_code = codes.BAD_REQUEST
        out_of_range_error = (
            f'Integer out of range ({max_num_results_int}) in form data part '
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        return out_of_range_error

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_include_target_data(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``include_target_data`` field is either an accepted value or
    not given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the ``include_target_data`` field is not an
        accepted value.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [include_target_data] = parsed.get('include_target_data', ['top'])
    include_target_data = include_target_data.lower()
    allowed_included_target_data = {'top', 'all', 'none'}
    if include_target_data in allowed_included_target_data:
        return wrapped(*args, **kwargs)

    unexpected_target_data_message = (
        f"Invalid value '{include_target_data}' in form data part "
        "'include_target_data'. "
        "Expecting one of the (unquoted) string values 'all', 'none' or 'top'."
    )
    context.status_code = codes.BAD_REQUEST
    return unexpected_target_data_message


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
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args
    date_header = request.headers['Date']

    for date_format in _accepted_date_formats():
        try:
            datetime.datetime.strptime(date_header, date_format)
        except ValueError:
            pass
        else:
            return wrapped(*args, **kwargs)

    context.status_code = codes.UNAUTHORIZED
    context.headers['WWW-Authenticate'] = 'VWS'
    text = 'Malformed date header.'
    content_type = 'text/plain; charset=ISO-8859-1'
    context.headers['Content-Type'] = content_type
    return text


@wrapt.decorator
def validate_date_in_range(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args
    date_header = request.headers['Date']

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
        return wrapped(*args, **kwargs)

    context.status_code = codes.FORBIDDEN

    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
    }
    return json_dump(body)


@wrapt.decorator
def validate_content_type_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the ``Content-Type`` header.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An ``UNSUPPORTED_MEDIA_TYPE`` response if the ``Content-Type`` header
        main part is not 'multipart/form-data'.
        A ``BAD_REQUEST`` response if the ``Content-Type`` header does not
        contain a boundary which is in the request body.
    """
    request, context = args

    main_value, pdict = cgi.parse_header(request.headers['Content-Type'])
    if main_value != 'multipart/form-data':
        context.status_code = codes.UNSUPPORTED_MEDIA_TYPE
        context.headers.pop('Content-Type')
        return ''

    if 'boundary' not in pdict:
        context.status_code = codes.BAD_REQUEST
        context.headers['Content-Type'] = 'text/html'
        return (
            'java.io.IOException: RESTEASY007550: '
            'Unable to get boundary for multipart'
        )

    if pdict['boundary'].encode() not in request.body:
        context.status_code = codes.BAD_REQUEST
        context.headers['Content-Type'] = 'text/html'
        return (
            'java.lang.RuntimeException: RESTEASY007500: '
            'Could find no Content-Disposition header within part'
        )

    return wrapped(*args, **kwargs)


@wrapt.decorator
def validate_accept_header(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
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
    request, context = args

    accept = request.headers.get('Accept')
    if accept in ('application/json', '*/*', None):
        return wrapped(*args, **kwargs)

    context.headers.pop('Content-Type')
    context.status_code = codes.NOT_ACCEPTABLE
    return ''


@wrapt.decorator
def validate_image_field_given(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate that the image field is given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if the image field is not given.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    if 'image' in parsed.keys():
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    return 'No image.'


@wrapt.decorator
def validate_extra_fields(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate that the no unknown fields are given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if extra fields are given.
    """
    request, context = args
    body_file = io.BytesIO(request.body)

    _, pdict = cgi.parse_header(request.headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    known_parameters = {'image', 'max_num_results', 'include_target_data'}

    if not parsed.keys() - known_parameters:
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    return 'Unknown parameters in the request.'
