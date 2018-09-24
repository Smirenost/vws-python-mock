"""
Utilities for tests.
"""

import io
import json
import random
from time import sleep
from typing import Any, Dict
from urllib.parse import urljoin

import requests
import timeout_decorator
from PIL import Image
from requests import Response
from requests_mock import DELETE, GET, POST, PUT
from urllib3.filepost import encode_multipart_formdata

from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database import VuforiaDatabase
from tests.mock_vws.utils.authorization import (
    authorization_header,
    rfc_1123_date,
)


class Endpoint:
    """
    Details of endpoints to be called in tests.
    """

    def __init__(
        self,
        prepared_request: requests.PreparedRequest,
        successful_headers_result_code: ResultCodes,
        successful_headers_status_code: int,
        access_key: bytes,
        secret_key: bytes,
    ) -> None:
        """
        Args:
            prepared_request: A request to make which would be successful.
            successful_headers_result_code: The expected result code if the
                example path is requested with the method.
            successful_headers_status_code: The expected status code if the
                example path is requested with the method.
            access_key: The access key used in the prepared request.
            secret_key: The secret key used in the prepared request.

        Attributes:
            prepared_request: A request to make which would be successful.
            successful_headers_result_code: The expected result code if the
                example path is requested with the method.
            successful_headers_status_code: The expected status code if the
                example path is requested with the method.
            auth_header_content_type: The content type to use for the
                `Authorization` header.
            access_key: The access key used in the prepared request.
            secret_key: The secret key used in the prepared request.
        """
        self.prepared_request = prepared_request
        self.successful_headers_status_code = successful_headers_status_code
        self.successful_headers_result_code = successful_headers_result_code
        headers = prepared_request.headers
        content_type = headers.get('Content-Type', '')
        content_type = content_type.split(';')[0]
        assert isinstance(content_type, str)
        self.auth_header_content_type: str = content_type
        self.access_key = access_key
        self.secret_key = secret_key


def add_target_to_vws(
    vuforia_database_keys: VuforiaDatabase,
    data: Dict[str, Any],
    content_type: str = 'application/json',
) -> Response:
    """
    Return a response from a request to the endpoint to add a target.

    Args:
        vuforia_database_keys: The credentials to use to connect to Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/targets'

    content = bytes(json.dumps(data), encoding='utf-8')

    authorization_string = authorization_header(
        access_key=vuforia_database_keys.server_access_key,
        secret_key=vuforia_database_keys.server_secret_key,
        method=POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': authorization_string,
        'Date': date,
        'Content-Type': content_type,
    }

    response = requests.request(
        method=POST,
        url=urljoin(base='https://vws.vuforia.com/', url=request_path),
        headers=headers,
        data=content,
    )

    return response


def get_vws_target(
    target_id: str,
    vuforia_database_keys: VuforiaDatabase,
) -> Response:
    """
    Return a response from a request to the endpoint to get a target record.

    Args:
        vuforia_database_keys: The credentials to use to connect to Vuforia.
        target_id: The ID of the target to return a record for.

    Returns:
        The response returned by the API.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=GET,
        content=b'',
        request_path='/targets/' + target_id,
    )
    return response


def database_summary(vuforia_database_keys: VuforiaDatabase) -> Response:
    """
    Return the response of a request to the database summary endpoint.

    Args:
        vuforia_database_keys: The credentials to use to connect to Vuforia.

    Returns:
        The response of a request to the database summary endpoint.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=GET,
        content=b'',
        request_path='/summary',
    )
    return response


@timeout_decorator.timeout(seconds=60 * 5)
def wait_for_target_processed(
    vuforia_database_keys: VuforiaDatabase,
    target_id: str,
) -> None:
    """
    Wait up to five minutes (arbitrary) for a target to get past the processing
    stage.

    Args:
        vuforia_database_keys: The credentials to use to connect to Vuforia.
        target_id: The ID of the target to wait for.

    Raises:
        TimeoutError: The target remained in the processing stage for more
            than five minutes.
    """
    while True:
        response = get_vws_target(
            target_id=target_id,
            vuforia_database_keys=vuforia_database_keys,
        )

        if response.json()['status'] != TargetStatuses.PROCESSING.value:
            return

        # We wait 0.2 seconds rather than less than that to decrease the number
        # of calls made to the API, to decrease the likelihood of hitting the
        # request quota.
        sleep(0.2)


def target_api_request(
    server_access_key: bytes,
    server_secret_key: bytes,
    method: str,
    content: bytes,
    request_path: str,
) -> Response:
    """
    Make a request to the Vuforia Target API.

    This uses `requests` to make a request against https://vws.vuforia.com.
    The content type of the request will be `application/json`.

    Args:
        server_access_key: A VWS server access key.
        server_secret_key: A VWS server secret key.
        method: The HTTP method which will be used in the request.
        content: The request body which will be used in the request.
        request_path: The path to the endpoint which will be used in the
            request.

    Returns:
        The response to the request made by `requests`.
    """
    date = rfc_1123_date()
    content_type = 'application/json'

    signature_string = authorization_header(
        access_key=server_access_key,
        secret_key=server_secret_key,
        method=method,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': signature_string,
        'Date': date,
        'Content-Type': content_type,
    }

    url = urljoin(base='https://vws.vuforia.com', url=request_path)

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        data=content,
    )

    return response


def delete_target(
    vuforia_database_keys: VuforiaDatabase,
    target_id: str,
) -> Response:
    """
    Delete a given target.

    Args:
        vuforia_database_keys: The credentials to the Vuforia target database
            to delete the target in.
        target_id: The ID of the target to delete.

    Returns:
        The response returned by the API.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=DELETE,
        content=b'',
        request_path=f'/targets/{target_id}',
    )

    return response


def update_target(
    vuforia_database_keys: VuforiaDatabase,
    data: Dict[str, Any],
    target_id: str,
    content_type: str = 'application/json',
) -> Response:
    """
    Make a request to the endpoint to update a target.

    Args:
        vuforia_database_keys: The credentials to use to connect to
            Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        target_id: The ID of the target to update.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/targets/' + target_id

    content = bytes(json.dumps(data), encoding='utf-8')

    authorization_string = authorization_header(
        access_key=vuforia_database_keys.server_access_key,
        secret_key=vuforia_database_keys.server_secret_key,
        method=PUT,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': authorization_string,
        'Date': date,
        'Content-Type': content_type,
    }

    response = requests.request(
        method=PUT,
        url=urljoin('https://vws.vuforia.com/', request_path),
        headers=headers,
        data=content,
    )

    return response


def list_targets(vuforia_database_keys: VuforiaDatabase) -> Response:
    """
    Get a list of targets.

    Args:
        vuforia_database_keys: The credentials to use to connect to
            Vuforia.

    Returns:
        The response returned by the API.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=GET,
        content=b'',
        request_path='/targets',
    )

    return response


def target_summary(
    vuforia_database_keys: VuforiaDatabase,
    target_id: str,
) -> Response:
    """
    Get a summary of a target.

    Args:
        vuforia_database_keys: The credentials to use to connect to
            Vuforia.
        target_id: The ID of the target to get a summary for.

    Returns:
        The response returned by the API.
    """
    response = target_api_request(
        server_access_key=vuforia_database_keys.server_access_key,
        server_secret_key=vuforia_database_keys.server_secret_key,
        method=GET,
        content=b'',
        request_path='/summary/' + target_id,
    )

    return response


def query(
    vuforia_database_keys: VuforiaDatabase,
    body: Dict[str, Any],
) -> Response:
    """
    Make a request to the endpoint to make an image recognition query.

    Args:
        vuforia_database_keys: The credentials to use to connect to
            Vuforia.
        body: The request body to send in ``multipart/formdata`` format.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/v1/query'
    content, content_type_header = encode_multipart_formdata(body)
    method = POST

    access_key = vuforia_database_keys.client_access_key
    secret_key = vuforia_database_keys.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type='multipart/form-data',
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': authorization_string,
        'Date': date,
        'Content-Type': content_type_header,
    }

    vwq_host = 'https://cloudreco.vuforia.com'
    response = requests.request(
        method=method,
        url=urljoin(base=vwq_host, url=request_path),
        headers=headers,
        data=content,
    )

    return response


def make_image_file(
    file_format: str,
    color_space: str,
    width: int,
    height: int,
) -> io.BytesIO:
    """
    Return an image file in the given format and color space.

    The image file is filled with randomly colored pixels.

    Args:
        file_format: See
            http://pillow.readthedocs.io/en/3.1.x/handbook/image-file-formats.html
        color_space: One of "L", "RGB", or "CMYK". "L" means greyscale.
        width: The width, in pixels of the image.
        height: The width, in pixels of the image.

    Returns:
        An image file in the given format and color space.
    """
    image_buffer = io.BytesIO()
    image = Image.new(color_space, (width, height))
    pixels = image.load()
    for i in range(height):
        for j in range(width):
            red = random.randint(0, 255)
            green = random.randint(0, 255)
            blue = random.randint(0, 255)
            if color_space != 'L':
                pixels[j, i] = (red, green, blue)
    image.save(image_buffer, file_format)
    image_buffer.seek(0)
    return image_buffer
