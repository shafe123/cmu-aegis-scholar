import sys
import os
from pathlib import Path

# This finds the absolute path to the 'aegis-scholar-api' directory
# based on the location of THIS conftest.py file.
service_root = Path(__file__).resolve().parents[3] / "services" / "aegis-scholar-api"

# Inject it into Python's search list
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))
