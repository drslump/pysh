#!/usr/bin/env python
#
# For developement:
#
#   pip install -e .[dev]
#
# For packaging first install the latest versions of the tooling:
#
#   pip install --upgrade pip setuptools wheel twine
#   pip install -e .[dev,build]
#

from setuptools import setup, find_packages
from distutils.util import convert_path

# Monkeypatches setuptools so it generates much faster entry points
# when installing from source. Normal installs via wheel already offer
# a fast launcher script. (https://github.com/pypa/setuptools/issues/510)
try:
    import fastentrypoints
except ImportError:
    from setuptools.command import easy_install
    import pkg_resources  # oh the irony :)
    easy_install.main(['fastentrypoints'])
    pkg_resources.require('fastentrypoints')
    import fastentrypoints


# Fetch version without importing the package
version_globals = {}  # type: ignore
with open(convert_path('pysh/version.py')) as fd:
    exec(fd.read(), version_globals)


setup(
    name='pysh',
    version=version_globals['__version__'],
    author='Iván Montes Velencoso',
    author_email='drslump@pollinimini.net',
    url='https://github.com/drslump/pysh',
    license='LICENSE.txt',
    description='Python shell scripting.',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    classifiers=(
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Unix Shell",
        "Topic :: Software Development",
        "Topic :: System :: Shells",
        "Topic :: System :: System Shells",
        "Topic :: Utilities",
    ),
    keywords='shell subprocess piping dsl',
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/drslump/pysh/issues',
        'Source': 'https://github.com/drslump/pysh',
        'Say Thanks!': 'https://twitter/drslump',
    },

    packages=find_packages(exclude=['docs', 'tests']),

    install_requires=[
        "docopt>=0.6.2<0.7",
        "braceexpand>=0.1.2<0.2",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-runner",
        ],
        "build": [
            # docs
            "sphinx",
            "sphinx_rtd_theme",
            "sphinxcontrib-plantuml",
            "recommonmark",
        ],
    },

    package_data={},
    data_files=[],

    entry_points={
        "console_scripts": [
            "pysh=pysh.__main__:main",
        ],
    }
)
