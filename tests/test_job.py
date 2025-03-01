from datetime import datetime
from supervaize_control.job import Job, JobStatus, JobResponse
from supervaize_control.job import JobContextModel


def create_test_job_context():
    return JobContextModel(
        workspace_id="test-workspace",
        job_id="test123",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
        mission_context={"test": "context"},
    )


def test_job_creation():
    job_context = create_test_job_context()

    response = JobResponse(
        job_ref="test123",
        status=JobStatus.START,
        message="Starting job",
        payload={"test": "data"},
    )

    job = Job.new(job_context=job_context, response=response)

    assert job.job_context == job_context
    assert job.status == JobStatus.START
    assert job.finished_at is None
    assert job.error is None
    assert job.result == {"test": "data"}


def test_job_add_response():
    job_context = create_test_job_context()

    # Create initial job
    start_response = JobResponse(
        job_ref="test123", status=JobStatus.START, message="Starting job", payload=None
    )
    job = Job.new(job_context=job_context, response=start_response)

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
    job_context = create_test_job_context()

    # Create job and add error response
    start_response = JobResponse(
        job_ref="test123", status=JobStatus.START, message="Starting job", payload=None
    )
    job = Job.new(job_context=job_context, response=start_response)

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
    job_context = create_test_job_context()

    response = JobResponse(
        job_ref="test123",
        status=JobStatus.HUM,
        message="Need human input",
        payload={"question": "What next?"},
    )

    job = Job.new(job_context=job_context, response=response)

    assert job.status == JobStatus.HUM
    assert job.finished_at is None
    assert job.result == {"question": "What next?"}
