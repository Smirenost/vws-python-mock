"""
A fake implementation of the Vuforia Web Services API.

See
https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API
"""

import base64
import datetime
import io
import itertools
import random
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import pytz
import wrapt
from PIL import Image
from requests import codes
from requests_mock import DELETE, GET, POST, PUT
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import (
    Route,
    json_dump,
    set_content_length_header,
    set_date_header,
)
from mock_vws._services_validators.exceptions import (
    AuthenticationFailure,
    BadImage,
    ContentLengthHeaderNotInt,
    ContentLengthHeaderTooLarge,
    Fail,
    ImageTooLarge,
    MetadataTooLarge,
    OopsErrorOccurredResponse,
    ProjectInactive,
    RequestTimeTooSkewed,
    TargetNameExist,
    UnknownTarget,
    UnnecessaryRequestBody,
)
from mock_vws.database import VuforiaDatabase

from ._services_validators import (
    validate_active_flag,
    validate_keys,
    validate_not_invalid_json,
    validate_project_state,
    validate_width,
)
from ._services_validators.auth_validators import (
    validate_access_key_exists,
    validate_auth_header_exists,
    validate_auth_header_has_signature,
    validate_authorization,
)
from ._services_validators.content_length_validators import (
    validate_content_length_header_is_int,
    validate_content_length_header_not_too_large,
    validate_content_length_header_not_too_small,
)
from ._services_validators.content_type_validators import (
    validate_content_type_header_given,
)
from ._services_validators.date_validators import (
    validate_date_format,
    validate_date_header_given,
    validate_date_in_range,
)
from ._services_validators.image_validators import (
    validate_image_color_space,
    validate_image_data_type,
    validate_image_encoding,
    validate_image_format,
    validate_image_is_image,
    validate_image_size,
)
from ._services_validators.metadata_validators import (
    validate_metadata_encoding,
    validate_metadata_size,
    validate_metadata_type,
)
from ._services_validators.name_validators import (
    validate_name_characters_in_range,
    validate_name_length,
    validate_name_type,
)
from ._services_validators.target_validators import validate_target_id_exists
from .target import Target

_TARGET_ID_PATTERN = '[A-Za-z0-9]+'


@wrapt.decorator
def update_request_count(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Add to the request count.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    instance.request_count += 1
    return wrapped(*args, **kwargs)


@wrapt.decorator
def handle_validators(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Add to the request count.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    _, context = args
    body: Dict[str, str] = {}
    try:
        return wrapped(*args, **kwargs)
    except (
        UnknownTarget,
        ProjectInactive,
        AuthenticationFailure,
        Fail,
        MetadataTooLarge,
        TargetNameExist,
        BadImage,
        ImageTooLarge,
        RequestTimeTooSkewed,
    ) as exc:
        context.status_code = exc.status_code
        return exc.response_text
    except OopsErrorOccurredResponse:
        context.status_code = codes.INTERNAL_SERVER_ERROR
        resources_dir = Path(__file__).parent / 'resources'
        filename = 'oops_error_occurred_response.html'
        oops_resp_file = resources_dir / filename
        content_type = 'text/html; charset=UTF-8'
        context.headers['Content-Type'] = content_type
        text = str(oops_resp_file.read_text())
        return text
    except ContentLengthHeaderTooLarge:
        context.status_code = codes.GATEWAY_TIMEOUT
        context.headers = {'Connection': 'keep-alive'}
        return ''
    except ContentLengthHeaderNotInt:
        context.status_code = codes.BAD_REQUEST
        context.headers = {'Connection': 'Close'}
        return ''
    except UnnecessaryRequestBody:
        context.status_code = codes.BAD_REQUEST
        context.headers.pop('Content-Type')
        return ''


@wrapt.decorator
def run_validators(
    wrapped: Callable[..., str],
    instance: Any,
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Add to the request count.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
    """
    request, _ = args
    _run_validators(
        request_text=request.text,
        request_headers=request.headers,
        request_body=request.body,
        request_method=request.method,
        request_path=request.path,
        databases=instance.databases,
    )
    return wrapped(*args, **kwargs)


ROUTES = set([])


def route(
    path_pattern: str,
    http_methods: List[str],
    mandatory_keys: Optional[Set[str]] = None,
    optional_keys: Optional[Set[str]] = None,
) -> Callable[..., Callable]:
    """
    Register a decorated method so that it can be recognized as a route.

    Args:
        path_pattern: The end part of a URL pattern. E.g. `/targets` or
            `/targets/.+`.
        http_methods: HTTP methods that map to the route function.
        mandatory_keys: Keys required by the endpoint.
        optional_keys: Keys which are not required by the endpoint but which
            are allowed.

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
                http_methods=http_methods,
            ),
        )

        # TODO:
        # * Switch all of these decorators to non-decorating functions
        # * Fix all their docstrings
        # * Move them (and their mock_vws dependencies) out of the mock_vws
        # directory
        # * Move the helper which runs them out of the mock_vws directory
        # * Use the new helper in the Flask mock

        key_validator = validate_keys(
            optional_keys=optional_keys or set([]),
            mandatory_keys=mandatory_keys or set([]),
        )
        decorators = [
            key_validator,
            run_validators,
            handle_validators,
            set_date_header,
            set_content_length_header,
            update_request_count,
        ]

        for decorator in decorators:
            method = decorator(method)

        return method

    return decorator


def _get_target_from_request(
    request_path: str,
    databases: List[VuforiaDatabase],
) -> Target:
    """
    Given a request path with a target ID in the path, and a list of databases,
    return the target with that ID from those databases.
    """
    split_path = request_path.split('/')
    target_id = split_path[-1]
    all_database_targets = itertools.chain.from_iterable(
        [database.targets for database in databases],
    )
    [target] = [
        target for target in all_database_targets
        if target.target_id == target_id
    ]
    return target


def _run_validators(
    request_text: str,
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Run all validators.

    Args:
        request_text: The content of the request.
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.
    """
    validate_auth_header_exists(request_headers=request_headers, )
    validate_auth_header_has_signature(request_headers=request_headers, )
    validate_access_key_exists(
        request_headers=request_headers,
        databases=databases,
    )
    validate_authorization(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_project_state(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_target_id_exists(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )
    validate_not_invalid_json(
        request_text=request_text,
        request_body=request_body,
        request_method=request_method,
    )
    validate_metadata_type(request_text=request_text, )
    validate_metadata_encoding(request_text=request_text, )
    validate_metadata_size(request_text=request_text, )
    validate_active_flag(request_text=request_text, )
    validate_image_data_type(request_text=request_text, )
    validate_image_encoding(request_text=request_text, )
    validate_image_is_image(request_text=request_text, )
    validate_image_format(request_text=request_text, )
    validate_image_color_space(request_text=request_text, )

    validate_image_size(request_text=request_text, )

    validate_name_type(request_text=request_text, )
    validate_name_length(request_text=request_text, )
    validate_name_characters_in_range(
        request_text=request_text,
        request_method=request_method,
        request_path=request_path,
    )

    validate_width(request_text=request_text, )
    validate_content_type_header_given(
        request_headers=request_headers,
        request_method=request_method,
    )

    validate_date_header_given(request_headers=request_headers, )

    validate_date_format(request_headers=request_headers, )
    validate_date_in_range(request_headers=request_headers, )

    validate_content_length_header_is_int(
        request_headers=request_headers,
        request_body=request_body,
    )
    validate_content_length_header_not_too_large(
        request_headers=request_headers,
        request_body=request_body,
    )

    validate_content_length_header_not_too_small(
        request_headers=request_headers,
        request_body=request_body,
    )


class MockVuforiaWebServicesAPI:
    """
    A fake implementation of the Vuforia Web Services API.

    This implementation is tied to the implementation of `requests_mock`.
    """

    def __init__(
        self,
        processing_time_seconds: Union[int, float],
    ) -> None:
        """
        Args:
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.

        Attributes:
            databases: Target databases.
            routes: The `Route`s to be used in the mock.
            request_count: The number of requests made to this API.
        """
        self.databases: List[VuforiaDatabase] = []
        self.routes: Set[Route] = ROUTES
        self._processing_time_seconds = processing_time_seconds
        self.request_count = 0

    @route(
        path_pattern='/targets',
        http_methods=[POST],
        mandatory_keys={'image', 'width', 'name'},
        optional_keys={'active_flag', 'application_metadata'},
    )
    def add_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Add a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Add-a-Target
        """
        name = request.json()['name']
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)

        targets = (
            target for target in database.targets if not target.delete_date
        )
        if any(target.name == name for target in targets):
            context.status_code = codes.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_NAME_EXIST.value,
            }
            return json_dump(body)

        active_flag = request.json().get('active_flag')
        if active_flag is None:
            active_flag = True

        image = request.json()['image']
        decoded = base64.b64decode(image)
        image_file = io.BytesIO(decoded)

        new_target = Target(
            name=request.json()['name'],
            width=request.json()['width'],
            image=image_file,
            active_flag=active_flag,
            processing_time_seconds=self._processing_time_seconds,
            application_metadata=request.json().get('application_metadata'),
        )
        database.targets.append(new_target)

        context.status_code = codes.CREATED
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_CREATED.value,
            'target_id': new_target.target_id,
        }
        return json_dump(body)

    @route(
        path_pattern=f'/targets/{_TARGET_ID_PATTERN}',
        http_methods=[DELETE],
    )
    def delete_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Delete a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Delete-a-Target
        """
        body: Dict[str, str] = {}
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )

        if target.status == TargetStatuses.PROCESSING.value:
            context.status_code = codes.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_STATUS_PROCESSING.value,
            }
            return json_dump(body)

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        target.delete_date = now

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
        }
        return json_dump(body)

    @route(path_pattern='/summary', http_methods=[GET])
    def database_summary(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a database summary report.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Database-Summary-Report
        """
        body: Dict[str, Union[str, int]] = {}

        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        active_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.SUCCESS.value
                and target.active_flag and not target.delete_date
            ],
        )

        failed_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.FAILED.value
                and not target.delete_date
            ],
        )

        inactive_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.SUCCESS.value
                and not target.active_flag and not target.delete_date
            ],
        )

        processing_images = len(
            [
                target for target in database.targets
                if target.status == TargetStatuses.PROCESSING.value
                and not target.delete_date
            ],
        )

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'name': database.database_name,
            'active_images': active_images,
            'inactive_images': inactive_images,
            'failed_images': failed_images,
            'target_quota': 1000,
            'total_recos': 0,
            'current_month_recos': 0,
            'previous_month_recos': 0,
            'processing_images': processing_images,
            'reco_threshold': 1000,
            'request_quota': 100000,
            # We have ``self.request_count`` but Vuforia always shows 0.
            # This was not always the case.
            'request_usage': 0,
        }
        return json_dump(body)

    @route(path_pattern='/targets', http_methods=[GET])
    def target_list(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a list of all targets.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Get-a-Target-List-for-a-Cloud-Database
        """
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        results = [
            target.target_id for target in database.targets
            if not target.delete_date
        ]

        body: Dict[str, Union[str, List[str]]] = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'results': results,
        }
        return json_dump(body)

    @route(path_pattern=f'/targets/{_TARGET_ID_PATTERN}', http_methods=[GET])
    def get_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get details of a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Record
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )

        target_record = {
            'target_id': target.target_id,
            'active_flag': target.active_flag,
            'name': target.name,
            'width': target.width,
            'tracking_rating': target.tracking_rating,
            'reco_rating': target.reco_rating,
        }

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
            'target_record': target_record,
            'status': target.status,
        }
        return json_dump(body)

    @route(
        path_pattern=f'/duplicates/{_TARGET_ID_PATTERN}',
        http_methods=[GET],
    )
    def get_duplicates(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get targets which may be considered duplicates of a given target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Check-for-Duplicate-Targets
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        other_targets = set(database.targets) - set([target])

        similar_targets: List[str] = [
            other.target_id for other in other_targets
            if Image.open(other.image) == Image.open(target.image) and
            TargetStatuses.FAILED.value not in (target.status, other.status)
            and TargetStatuses.PROCESSING.value != other.status
            and other.active_flag
        ]

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'similar_targets': similar_targets,
        }

        return json_dump(body)

    @route(
        path_pattern=f'/targets/{_TARGET_ID_PATTERN}',
        http_methods=[PUT],
        optional_keys={
            'active_flag',
            'application_metadata',
            'image',
            'name',
            'width',
        },
    )
    def update_target(
        self,
        request: _RequestObjectProxy,
        context: _Context,
    ) -> str:
        """
        Update a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Update-a-Target
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        body: Dict[str, str] = {}
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)

        if target.status != TargetStatuses.SUCCESS.value:
            context.status_code = codes.FORBIDDEN
            body = {
                'transaction_id': uuid.uuid4().hex,
                'result_code': ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
            }
            return json_dump(body)

        if 'width' in request.json():
            target.width = request.json()['width']

        if 'active_flag' in request.json():
            active_flag = request.json()['active_flag']
            if active_flag is None:
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.FAIL.value,
                }
                context.status_code = codes.BAD_REQUEST
                return json_dump(body)
            target.active_flag = active_flag

        if 'application_metadata' in request.json():
            if request.json()['application_metadata'] is None:
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.FAIL.value,
                }
                context.status_code = codes.BAD_REQUEST
                return json_dump(body)
            application_metadata = request.json()['application_metadata']
            target.application_metadata = application_metadata

        if 'name' in request.json():
            name = request.json()['name']
            other_targets = set(database.targets) - set([target])
            if any(
                other.name == name for other in other_targets
                if not other.delete_date
            ):
                context.status_code = codes.FORBIDDEN
                body = {
                    'transaction_id': uuid.uuid4().hex,
                    'result_code': ResultCodes.TARGET_NAME_EXIST.value,
                }
                return json_dump(body)
            target.name = name

        if 'image' in request.json():
            image = request.json()['image']
            decoded = base64.b64decode(image)
            image_file = io.BytesIO(decoded)
            target.image = image_file

        # In the real implementation, the tracking rating can stay the same.
        # However, for demonstration purposes, the tracking rating changes but
        # when the target is updated.
        available_values = list(set(range(6)) - set([target.tracking_rating]))
        target.processed_tracking_rating = random.choice(available_values)

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        target.last_modified_date = now

        body = {
            'result_code': ResultCodes.SUCCESS.value,
            'transaction_id': uuid.uuid4().hex,
        }
        return json_dump(body)

    @route(path_pattern=f'/summary/{_TARGET_ID_PATTERN}', http_methods=[GET])
    def target_summary(
        self,
        request: _RequestObjectProxy,
        context: _Context,  # pylint: disable=unused-argument
    ) -> str:
        """
        Get a summary report for a target.

        Fake implementation of
        https://library.vuforia.com/articles/Solution/How-To-Use-the-Vuforia-Web-Services-API.html#How-To-Retrieve-a-Target-Summary-Report
        """
        target = _get_target_from_request(
            request_path=request.path,
            databases=self.databases,
        )
        database = get_database_matching_server_keys(
            request_headers=request.headers,
            request_body=request.body,
            request_method=request.method,
            request_path=request.path,
            databases=self.databases,
        )

        assert isinstance(database, VuforiaDatabase)
        body = {
            'status': target.status,
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.SUCCESS.value,
            'database_name': database.database_name,
            'target_name': target.name,
            'upload_date': target.upload_date.strftime('%Y-%m-%d'),
            'active_flag': target.active_flag,
            'tracking_rating': target.tracking_rating,
            'total_recos': 0,
            'current_month_recos': 0,
            'previous_month_recos': 0,
        }
        return json_dump(body)
