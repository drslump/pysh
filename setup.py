from setuptools import setup
from distutils.util import convert_path


# Fetch version without importing the package
version_globals = {}
with open(convert_path('pysh/version.py')) as fd:
    exec(fd.read(), version_globals)


setup(
    name='pysh',
    version=version_globals['__version__'],
    author='Iván Montes Velencoso',
    author_email='drslump@pollinimini.net',
    packages=['pysh'],
    url='https://github.com/drslump/pysh',
    license='LICENSE.txt',
    description='Python shell scripting.',
    long_description=open('README.md').read(),
    entry_points = {
        'console_scripts': [
            'pysh = pysh.__main__:main',
        ],
    },
    install_requires=[
        "six",
        "docopt == 0.6.2",
    ],
    setup_requires=[
        "pytest-runner",
    ],
    test_requires=[
        "pytest",
    ]
)
