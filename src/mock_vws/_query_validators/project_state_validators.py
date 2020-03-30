"""
Validators for the project state.
"""

from typing import Dict, List

from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._query_validators.exceptions import InactiveProject
from mock_vws.database import VuforiaDatabase
from mock_vws.states import States


def validate_project_state(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the state of the project.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.

    Raises:
        The result of calling the endpoint.
        A `FORBIDDEN` response with an InactiveProject result code if the
        project is inactive.
    """
    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)
    if database.state != States.PROJECT_INACTIVE:
        return

    raise InactiveProject
