Differences between the mock and the real Vuforia Web Services
==============================================================

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/adamtheturtle/vws-python-mock/issues>`__.
There is no attempt to make the image matching realistic.

Speed and summary accuracy
~~~~~~~~~~~~~~~~~~~~~~~~~~

The mock responds much more quickly than the real Vuforia Web Services.

Targets in the mock are set to ‘processing’ for half a second by default.
This is customisable, with the ``processing_time_seconds`` parameter.
In the real Vuforia Web Services, the processing stage takes varying lengths of time.

The database summary in the real Vuforia Web Services takes some time to account for images.
Sometimes the real summary skips image states such as the processing state.
The mock is accurate immediately.

Image quality and ratings
~~~~~~~~~~~~~~~~~~~~~~~~~

Targets are assigned a rating between 0 and 5 of how good they are for tracking purposes.
In the mock this is a random number between 0 and 5.

Image targets which are not suited to detection are given ‘failed’ statuses.
The criteria for these images is not defined by the Vuforia documentation.
The mock is more forgiving than the real Vuforia Web Services.
Therefore, an image given a ‘success’ status by the mock may not be given a ‘success’ status by the real Vuforia Web Services.

When updating an image for a target on the real Vuforia Web Services, the rating may stay the same.
The mock changes the rating for a target to a different random number when the image is changed.

Matching targets in the processing state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Matching a target which is in the processing state sometimes returns a successful response with no results.
Sometimes a 500 (INTERNAL SERVER ERROR) response is given.
The mock always gives a 500 response.

Matching deleted targets
~~~~~~~~~~~~~~~~~~~~~~~~

Matching a target which has been deleted returns a 500 (INTERNAL SERVER ERROR) response within the first few seconds.
This timeframe is not consistent on the real Vuforia Web Services.
On the mock, this timeframe is three seconds by default.
``MockVWS`` takes a parameter ``query_recognizes_deletion_seconds`` to change this.

Accepted date formats for the Query API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Query API documentation is not clear on which date formats are expected exactly in the ``Date`` header.
The mock is strict.
That is, it accepts only a few date formats, and rejects all others.
If you find a date format which is accepted by the real Query API but rejected by the mock, please create a GitHub issue.

Targets stuck in processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the real Vuforia Web Services, targets sometimes get stuck in the processing state.
For example, targets with the name ``\uffff`` get stuck in the processing state.
On the mock, no targets get stuck in the processing state.

Database summary quotas
~~~~~~~~~~~~~~~~~~~~~~~

The database summary endpoint returns quotas which match the quotas given for a free license.
