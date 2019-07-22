#!/usr/bin/env python3
import io
import os
import sys
from shutil import rmtree
from setuptools import find_packages, setup, Command

here = os.path.abspath(os.path.dirname(__file__))

with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev
"""class UploadCommand(Command):
    \"""Support setup.py upload.""\"

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        \"""Prints things in bold.""\"
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()
#"""

setup(
    name='NuEdit',
    version='0.4.0',
    author='Nicolai Søborg',
    author_email='nuedit@xn--sb-lka.org',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=3.5.0',
    url='https://xn--sb-lka.org/NicolaiSoeborg/NuEdit/',
    py_modules=['nuedit'],
    # entry_points={
    #     'console_scripts': ['mycli=mymodule:cli'],
    # },
    #package_data={'': ['xi-editor/rust/target/release/xi-core']},
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 1 - Planning",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Text Editors",
    ],
    # $ setup.py publish support.
    #cmdclass={
    #    'upload': UploadCommand,
    #},
)
