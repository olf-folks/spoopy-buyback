from .development import *
import os

# Override database to use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Use in-memory database for faster tests
    }
}

# Use custom pytest test runner
TEST_RUNNER = 'config.test_runner.PytestTestRunner'

# Disable migrations for faster test runs (pytest-django handles this, but explicit is good)
# This is already handled by pytest.ini with --nomigrations

print("Django test settings loaded successfully")

