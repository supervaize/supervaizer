from datetime import datetime
from supervaize_control.job import Job, JobStatus, JobResponse
from supervaize_control.job import JobContext


def create_test_supervaize_context():
    return JobContext(
        workspace_id="test-workspace",
        job_id="test123",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
        mission_context={"test": "context"},
    )


def test_job_creation():
    supervaize_context = create_test_supervaize_context()

    response = JobResponse(
        job_ref="test123",
        status=JobStatus.IN_PROGRESS,
        message="Starting job",
        payload={"test": "data"},
    )

    job = Job.new(supervaize_context=supervaize_context)

    job.add_response(response)
    assert job.supervaize_context == supervaize_context
    assert job.status == JobStatus.IN_PROGRESS
    assert job.finished_at is None
    assert job.error is None
    assert job.payload == {"test": "data"}


def test_job_add_response():
    supervaize_context = create_test_supervaize_context()

    # Create initial job

    job = Job.new(supervaize_context=supervaize_context)

    # Add intermediary response
    inter_response = JobResponse(
        job_ref="test123",
        status=JobStatus.PAUSED,
        message="Processing",
        payload={"progress": "50%"},
    )
    job.add_response(inter_response)

    assert job.status == JobStatus.PAUSED
    assert job.finished_at is None

    # Add final response
    final_response = JobResponse(
        job_ref="test123",
        status=JobStatus.COMPLETED,
        message="Complete",
        payload={"result": "success"},
    )
    job.add_response(final_response)

    assert job.status == JobStatus.COMPLETED
    assert job.result == {"result": "success"}
    assert isinstance(job.finished_at, datetime)


def test_job_error_response():
    supervaize_context = create_test_supervaize_context()

    # Create job and add error response
    job = Job.new(supervaize_context=supervaize_context)

    error_response = JobResponse(
        job_ref="test123",
        status=JobStatus.FAILED,
        message="Something went wrong",
        payload=None,
    )
    job.add_response(error_response)

    assert job.status == JobStatus.FAILED
    assert job.error == "Something went wrong"
    assert isinstance(job.finished_at, datetime)


def test_job_human_request():
    supervaize_context = create_test_supervaize_context()
    job = Job.new(supervaize_context=supervaize_context)
    assert job.status == JobStatus.IN_PROGRESS

    response = JobResponse(
        job_ref="test123",
        status=JobStatus.WAITING,
        message="Need human input",
        payload={"question": "What next?"},
    )

    job.add_response(response)

    assert job.status == JobStatus.WAITING
    assert job.finished_at is None
    assert job.payload == {"question": "What next?"}
