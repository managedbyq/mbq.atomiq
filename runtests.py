import os
import sys

import django
from django.test.runner import DiscoverRunner


def run_tests():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
    django.setup()
    test_runner = DiscoverRunner(keepdb=True)
    failures = test_runner.run_tests(['tests'])
    sys.exit(bool(failures))


if __name__ == '__main__':
    run_tests()
