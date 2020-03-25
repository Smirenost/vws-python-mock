"""
Exceptions to raise from validators.
"""

import uuid

from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class UnknownTarget(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'UnknownTarget'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.NOT_FOUND
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.UNKNOWN_TARGET.value,
        }
        self.response_text = json_dump(body)


class ProjectInactive(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'ProjectInactive'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.PROJECT_INACTIVE.value,
        }
        self.response_text = json_dump(body)


class AuthenticationFailure(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNAUTHORIZED
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        self.response_text = json_dump(body)


class Fail(Exception):
    """
    Exception raised when Vuforia returns a response with a result code 'Fail'.
    """

    def __init__(self, status_code: int) -> None:
        super().__init__()
        self.status_code = status_code
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        self.response_text = json_dump(body)


class MetadataTooLarge(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'MetadataTooLarge'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.METADATA_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)


class TargetNameExist(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'TargetNameExist'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_NAME_EXIST.value,
        }
        self.response_text = json_dump(body)


class OopsErrorOccurredResponse(Exception):
    """
    Exception raised when VWS returns an HTML page which says "Oops, an error
    occurred".

    This has been seen to happen when the given name includes a bad character.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.INTERNAL_SERVER_ERROR


class BadImage(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'BadImage'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.BAD_IMAGE.value,
        }
        self.response_text = json_dump(body)


class ImageTooLarge(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'ImageTooLarge'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.IMAGE_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)


class RequestTimeTooSkewed(Exception):
    """
    Exception raised when Vuforia returns a response with a result code
    'RequestTimeTooSkewed'.
    """

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body)


class ContentLengthHeaderTooLarge(Exception):
    """
    Exception raised when the given content length header is too large.
    """


class ContentLengthHeaderNotInt(Exception):
    """
    Exception raised when the given content length header is not an integer.
    """


class UnnecessaryRequestBody(Exception):
    """
    Exception raised when a request body is given but not necessary.
    """
