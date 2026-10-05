"""Firestore database client utility for Recipe Assistant."""

from google.cloud import firestore

# Hardcoded project ID string (avoids project number issues from google.auth.default() on Agent Platform)
PROJECT_ID = "qwiklabs-gcp-01-57f938af240a"


def get_firestore_client() -> firestore.Client:
    """Returns an initialized Firestore client configured for the project."""
    return firestore.Client(project=PROJECT_ID)
