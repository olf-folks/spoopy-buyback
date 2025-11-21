"""
Custom Django test runner that uses pytest instead of unittest.
Based on Django documentation: https://docs.djangoproject.com/en/5.2/topics/testing/advanced/#using-different-testing-frameworks
"""
import pytest
import os
import sys


class PytestTestRunner:
    """
    Test runner that uses pytest to discover and run tests.
    
    This class follows Django's test runner interface as documented at:
    https://docs.djangoproject.com/en/5.2/topics/testing/advanced/#using-different-testing-frameworks
    """

    def __init__(self, verbosity=1, interactive=True, keepdb=False, **kwargs):
        """
        Initialize the test runner.
        
        Args:
            verbosity: Verbosity level (0=quiet, 1=normal, 2=verbose)
            interactive: Whether to run in interactive mode
            keepdb: Whether to keep the test database after tests
        """
        self.verbosity = verbosity
        self.interactive = interactive
        self.keepdb = keepdb

    def run_tests(self, test_labels, **kwargs):
        """
        Run pytest with the given test labels.
        
        Args:
            test_labels: List of test labels (e.g., ['buyback', 'buyback.tests.test_utils'])
            **kwargs: Additional keyword arguments
            
        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Ensure we're using the test settings
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')
        
        argv = []
        
        # Add verbosity
        if self.verbosity == 0:
            argv.append('-q')
        elif self.verbosity == 2:
            argv.append('-vv')
        else:
            argv.append('-v')
        
        # Add keepdb flag if requested
        if self.keepdb:
            argv.append('--reuse-db')
        
        # Add nomigrations for speed
        argv.append('--nomigrations')
        
        # Convert Django test labels to pytest paths
        if test_labels:
            pytest_paths = []
            for label in test_labels:
                if '.' in label:
                    # Convert 'buyback.tests.test_utils' to 'buyback/tests/test_utils.py'
                    parts = label.split('.')
                    pytest_paths.append('/'.join(parts) + '.py')
                else:
                    # If it's just an app name, add tests directory
                    pytest_paths.append(f'{label}/tests/')
            argv.extend(pytest_paths)
        else:
            # Default to running all tests
            argv.append('buyback/tests/')
        
        # Run pytest
        exit_code = pytest.main(argv)
        return exit_code
