"""Disposable local app for browser integration checks; never the product database."""
from pathlib import Path
import os
from backend.api.app import create_app
root=Path(__file__).resolve().parents[2]
path=Path(os.environ['SHARE_TEST_DB']).resolve()
if not path.is_relative_to(root/'.runtime'):
    raise ValueError('Browser test database must remain in .runtime')
app=create_app(path)
