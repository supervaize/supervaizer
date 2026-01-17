#!/usr/bin/env python3
"""
Local Docker Testing Script

This script demonstrates how to test Supervaizer deployments locally using Docker.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run local Docker tests."""
    print("🐳 Supervaizer Local Docker Testing")
    print("=" * 50)

    # Check if we're in a Supervaizer project
    if not Path("supervaizer_control.py").exists():
        print("❌ Error: supervaizer_control.py not found")
        print("   Please run this script from a Supervaizer project directory")
        sys.exit(1)

    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        print("✅ Docker is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Docker is not available")
        print("   Please install Docker and ensure it's running")
        sys.exit(1)

    # Check if docker-compose is available
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        print("✅ Docker Compose is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Docker Compose is not available")
        print("   Please install Docker Compose")
        sys.exit(1)

    print("\n🚀 Starting local test...")

    # Run the test command
    try:
        cmd = [
            sys.executable,
            "-m",
            "supervaizer",
            "deploy",
            "local",
            "--port",
            "8000",
            "--generate-api-key",
            "--verbose",
        ]

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True)

        print("\n✅ Local test completed successfully!")
        print("\n📋 Next steps:")
        print("   • Visit http://localhost:8000/docs for API documentation")
        print("   • Visit http://localhost:8000/.well-known/health for health check")
        print(
            "   • Run 'docker-compose -f .deployment/docker-compose.yml down' to stop"
        )

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Test failed with exit code {e.returncode}")
        print("\n🔍 Troubleshooting:")
        print(
            "   • Check Docker logs: docker-compose -f .deployment/docker-compose.yml logs"
        )
        print("   • Ensure port 8000 is not in use")
        print("   • Verify supervaizer_control.py is properly configured")
        sys.exit(1)


if __name__ == "__main__":
    main()
