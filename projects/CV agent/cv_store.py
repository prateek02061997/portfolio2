"""
cv_store.py — persistent CV data management.

- load_cv()  → returns current CV dict (user_cv.json if customised, else cv_data.py defaults)
- save_cv()  → saves updates to user_cv.json
- reset_cv() → deletes user_cv.json, reverts to cv_data.py defaults
"""

import json
import os
import copy

from cv_data import CV_DATA as _DEFAULT

STORE_PATH = os.path.join(os.path.dirname(__file__), 'user_cv.json')


def load_cv() -> dict:
    """Return the current CV dict. Loads user_cv.json if it exists, else returns defaults."""
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return copy.deepcopy(_DEFAULT)


def save_cv(data: dict) -> None:
    """Persist the CV dict to user_cv.json."""
    with open(STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def reset_cv() -> None:
    """Delete user_cv.json, reverting to cv_data.py defaults."""
    if os.path.exists(STORE_PATH):
        os.remove(STORE_PATH)
