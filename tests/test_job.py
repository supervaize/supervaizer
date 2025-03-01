from datetime import datetime
from supervaize_control.job import Job, JobStatus, JobResponse


def test_job_creation():
    response = JobResponse(
        job_ref="test123",
        status=JobStatus.START,
        message="Starting job",
        payload={"test": "data"},
    )

    job = Job.new(response)

    assert job.id == "test123"
    assert job.status == JobStatus.START
    assert isinstance(job.started_at, datetime)
    assert job.finished_at is None
    assert job.error is None
    assert job.result == {"test": "data"}


def test_job_add_response():
    # Create initial job
    start_response = JobResponse(
        job_ref="test123", status=JobStatus.START, message="Starting job", payload=None
    )
    job = Job.new(start_response)

    # Add intermediary response
    inter_response = JobResponse(
        job_ref="test123",
        status=JobStatus.INTERMEDIARY,
        message="Processing",
        payload={"progress": "50%"},
    )
    job.add_response(inter_response)

    assert job.status == JobStatus.INTERMEDIARY
    assert job.finished_at is None

    # Add final response
    final_response = JobResponse(
        job_ref="test123",
        status=JobStatus.FINAL,
        message="Complete",
        payload={"result": "success"},
    )
    job.add_response(final_response)

    assert job.status == JobStatus.FINAL
    assert job.result == {"result": "success"}
    assert isinstance(job.finished_at, datetime)


def test_job_error_response():
    # Create job and add error response
    start_response = JobResponse(
        job_ref="test123", status=JobStatus.START, message="Starting job", payload=None
    )
    job = Job.new(start_response)

    error_response = JobResponse(
        job_ref="test123",
        status=JobStatus.ERROR,
        message="Something went wrong",
        payload=None,
    )
    job.add_response(error_response)

    assert job.status == JobStatus.ERROR
    assert job.error == "Something went wrong"
    assert isinstance(job.finished_at, datetime)


def test_job_human_request():
    response = JobResponse(
        job_ref="test123",
        status=JobStatus.HUM,
        message="Need human input",
        payload={"question": "What next?"},
    )

    job = Job.new(response)

    assert job.status == JobStatus.HUM
    assert job.finished_at is None
    assert job.result == {"question": "What next?"}
