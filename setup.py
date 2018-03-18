import codecs
import os
import re

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
print("here:", here)
def read(*parts):
    return codecs.open(os.path.join(here, *parts), 'r').read()

def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

long_description = read('README.md')

setup(
    name='toggl-tools',
    version=find_version('toggl-tools', '__init__.py'),
    description='Python tools for toggl time entries. Includes a tool to split a large time entry into smaller ones.',
    long_description=long_description,
    url='https://github.com/JeroenvdV/toggl-tools',
    author='JeroenvdV',
    author_email='jeroenvdv@example.com',
    license='MIT',
    packages=['toggl-tools'],
    dependency_links=['git+https://github.com/JeroenvdV/TogglPy.git/@master#egg=togglpy-0'],
    install_requires=[
        'pyyaml',
        'python-dateutil',
        'TogglPy'
    ],
    zip_safe=False
)
