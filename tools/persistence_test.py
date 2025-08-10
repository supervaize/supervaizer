#!/usr/bin/env python3

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime

from supervaizer.job import Job, JobContext
from supervaizer.lifecycle import EntityStatus
from supervaizer.storage import StorageManager


def test_persistence() -> None:
    print("=== Testing Persistence ===")

    # Create storage manager
    storage = StorageManager()
    print(f"Storage path: {storage.db_path}")

    # Clear existing data
    storage.reset_storage()

    # Create test job context
    job_context = JobContext(
        workspace_id="test-workspace",
        job_id="test-job-456",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
    )

    # Create test job
    print("Creating test job...")
    _job = Job(
        id="test-job-456",
        name="Test Job for Persistence",
        agent_name="test-agent",
        status=EntityStatus.STOPPED,
        job_context=job_context,
    )

    # Check if job was saved immediately
    print("Checking if job was saved immediately...")
    saved_job = storage.get_object_by_id("Job", "test-job-456")
    print(f"Job saved: {saved_job is not None}")

    # Check the file content immediately
    print(f"Checking file immediately: {storage.db_path}")
    try:
        with open(storage.db_path, "r") as f:
            content = f.read()
            print(f"File size: {len(content)} characters")
            if content and len(content) > 100:
                print("File contains data! ✅")
                # Check if it contains our job
                if "test-job-456" in content:
                    print("Job is persisted in file! ✅")
                else:
                    print("Job NOT found in file ❌")
            else:
                print("File is empty or too small ❌")
    except Exception as e:
        print(f"Error reading file: {e}")

    # Simulate server restart by creating a new storage manager
    print("\n--- Simulating Server Restart ---")
    print("Creating new storage manager...")
    new_storage = StorageManager()

    # Try to load the job
    print("Loading job after 'restart'...")
    loaded_job = new_storage.get_object_by_id("Job", "test-job-456")
    if loaded_job:
        print("Job successfully loaded after restart! ✅")
        print(f"Loaded job name: {loaded_job['name']}")
    else:
        print("Job NOT found after restart ❌")

    # Get all jobs
    all_jobs = new_storage.get_objects("Job")
    print(f"Total jobs in storage: {len(all_jobs)}")


if __name__ == "__main__":
    test_persistence()
