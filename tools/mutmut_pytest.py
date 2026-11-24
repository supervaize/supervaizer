"""Avoid macOS system proxy lookup after mutmut forks test processes."""

import os

os.environ.setdefault("no_proxy", "*")
