"""
A fake implementation of the Vuforia Web Query API.

See
https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query
"""

import base64
import cgi
import datetime
import io
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple, Union

import pytz
import wrapt
from requests import codes
from requests_mock import POST
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._mock_common import (
    Route,
    json_dump,
    parse_multipart,
    set_content_length_header,
    set_date_header,
)
from mock_vws._query_validators import run_query_validators
from mock_vws._query_validators.exceptions import (
    AuthenticationFailure,
    AuthenticationFailureGoodFormatting,
    AuthHeaderMissing,
    BadImage,
    BoundaryNotInBody,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
    DateFormatNotValid,
    DateHeaderNotGiven,
    ImageNotGiven,
    InactiveProject,
    InvalidAcceptHeader,
    InvalidIncludeTargetData,
    InvalidMaxNumResults,
    MalformedAuthHeader,
    MaxNumResultsOutOfRange,
    NoBoundaryFound,
    QueryOutOfBounds,
    RequestTimeTooSkewed,
    UnknownParameters,
    UnsupportedMediaType,
)
from mock_vws.database import VuforiaDatabase

ROUTES = set([])


@wrapt.decorator
def run_validators(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Run all validators for the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    request, context = args
    try:
        run_query_validators(
            request_path=request.path,
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            databases=instance.databases,
        )
    except DateHeaderNotGiven as exc:
        content_type = 'text/plain; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        context.status_code = exc.status_code
        return exc.response_text
    except (
        AuthHeaderMissing,
        DateFormatNotValid,
        MalformedAuthHeader,
    ) as exc:
        content_type = 'text/plain; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        context.headers['WWW-Authenticate'] = 'VWS'
        context.status_code = exc.status_code
        return exc.response_text
    except (AuthenticationFailure, AuthenticationFailureGoodFormatting) as exc:
        context.headers['WWW-Authenticate'] = 'VWS'
        context.status_code = exc.status_code
        return exc.response_text
    except (
        RequestTimeTooSkewed,
        ImageNotGiven,
        UnknownParameters,
        InactiveProject,
        InvalidIncludeTargetData,
        InvalidMaxNumResults,
        MaxNumResultsOutOfRange,
        BadImage,
    ) as exc:
        context.status_code = exc.status_code
        return exc.response_text
    except (UnsupportedMediaType, InvalidAcceptHeader) as exc:
        context.headers.pop('Content-Type')
        context.status_code = exc.status_code
        return exc.response_text
    except (NoBoundaryFound, BoundaryNotInBody) as exc:
        content_type = 'text/html;charset=UTF-8'
        context.headers['Content-Type'] = content_type
        context.status_code = exc.status_code
        return exc.response_text
    except QueryOutOfBounds as exc:
        content_type = 'text/html; charset=ISO-8859-1'
        context.headers['Content-Type'] = content_type
        cache_control = 'must-revalidate,no-cache,no-store'
        context.headers['Cache-Control'] = cache_control
        context.status_code = exc.status_code
        return exc.response_text
    except ContentLengthHeaderNotInt as exc:
        context.headers = {'Connection': 'Close'}
        context.status_code = exc.status_code
        return exc.response_text
    except ContentLengthHeaderTooLarge as exc:
        context.headers = {'Connection': 'keep-alive'}
        context.status_code = exc.status_code
        return exc.response_text

    return wrapped(*args, **kwargs)


def route(
    path_pattern: str,
    http_methods: Set[str],
) -> Callable[..., Callable]:
    """
    Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.

    Returns:
        A decorator which takes methods and makes them recognizable as routes.
    """

    def decorator(method: Callable[..., str]) -> Callable[..., str]:
        """
        Register a decorated method so that it can be recognized as a route.

        Returns:
            The given `method` with multiple changes, including added
            validators.
        """
        ROUTES.add(
            Route(
                route_name=method.__name__,
                path_pattern=path_pattern,
                http_methods=frozenset(http_methods),
            ),
        )

        decorators = [
            run_validators,
            set_date_header,
            set_content_length_header,
        ]

        for decorator in decorators:
            method = decorator(method)

        return method

    return decorator


class MockVuforiaWebQueryAPI:
    """
    A fake implementation of the Vuforia Web Query API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        query_recognizes_deletion_seconds: Union[int, float],
        query_processes_deletion_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            query_recognizes_deletion_seconds: The number of seconds after a
                target has been deleted that the query endpoint will still
                recognize the target for.
            query_processes_deletion_seconds: The number of seconds after a
                target deletion is recognized that the query endpoint will
                return a 500 response on a match.

        Attributes:
            routes: The `Route`s to be used in the mock.
            databases: Target databases.
        """
        self.routes: Set[Route] = ROUTES
        self.databases: Set[VuforiaDatabase] = set([])
        self._query_processes_deletion_seconds = (
            query_processes_deletion_seconds
        )
        self._query_recognizes_deletion_seconds = (
            query_recognizes_deletion_seconds
        )

    @route(path_pattern='/v1/query', http_methods={POST})
    def query(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Perform an image recognition query.
        """
        body_file = io.BytesIO(request.body)

        _, pdict = cgi.parse_header(request.headers['Content-Type'])
        parsed = parse_multipart(
            fp=body_file,
            pdict={
                'boundary': pdict['boundary'].encode(),
            },
        )

        [max_num_results] = parsed.get('max_num_results', ['1'])

        [include_target_data] = parsed.get('include_target_data', ['top'])
        include_target_data = include_target_data.lower()

        [image] = parsed['image']
        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)

        processing_timedelta = datetime.timedelta(
            seconds=self._query_processes_deletion_seconds,
        )

        recognition_timedelta = datetime.timedelta(
            seconds=self._query_recognizes_deletion_seconds,
        )

        database = get_database_matching_client_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)

        matching_targets = [
            target for target in database.targets
            if target.image.getvalue() == image
        ]

        not_deleted_matches = [
            target for target in matching_targets
            if target.active_flag and not target.delete_date
            and target.status == TargetStatuses.SUCCESS.value
        ]

        deletion_not_recognized_matches = [
            target for target in matching_targets
            if target.active_flag and target.delete_date and
            (now - target.delete_date) < recognition_timedelta
        ]

        matching_targets_with_processing_status = [
            target for target in matching_targets
            if target.status == TargetStatuses.PROCESSING.value
        ]

        active_matching_targets_delete_processing = [
            target for target in matching_targets if target.active_flag
            and target.delete_date and (now - target.delete_date) <
            (recognition_timedelta + processing_timedelta)
            and target not in deletion_not_recognized_matches
        ]

        if (
            matching_targets_with_processing_status
            or active_matching_targets_delete_processing
        ):
            # We return an example 500 response.
            # Each response given by Vuforia is different.
            #
            # Sometimes Vuforia will ignore matching targets with the
            # processing status, but we choose to:
            # * Do the most unexpected thing.
            # * Be consistent with every response.
            resources_dir = Path(__file__).parent / 'resources'
            filename = 'match_processing_response'
            match_processing_resp_file = resources_dir / filename
            context.status_code = codes.INTERNAL_SERVER_ERROR
            cache_control = 'must-revalidate,no-cache,no-store'
            context.headers['Cache-Control'] = cache_control
            content_type = 'text/html; charset=ISO-8859-1'
            context.headers['Content-Type'] = content_type
            return Path(match_processing_resp_file).read_text()

        matches = not_deleted_matches + deletion_not_recognized_matches

        results: List[Dict[str, Any]] = []
        for target in matches:
            target_timestamp = target.last_modified_date.timestamp()
            if target.application_metadata is None:
                application_metadata = None
            else:
                application_metadata = base64.b64encode(
                    decode_base64(encoded_data=target.application_metadata),
                ).decode('ascii')
            target_data = {
                'target_timestamp': int(target_timestamp),
                'name': target.name,
                'application_metadata': application_metadata,
            }

            if include_target_data == 'all':
                result = {
                    'target_id': target.target_id,
                    'target_data': target_data,
                }
            elif include_target_data == 'top' and not results:
                result = {
                    'target_id': target.target_id,
                    'target_data': target_data,
                }
            else:
                result = {
                    'target_id': target.target_id,
                }

            results.append(result)

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'results': results[:int(max_num_results)],
            'query_id': uuid.uuid4().hex,
        }

        value = json_dump(body)
        return value
