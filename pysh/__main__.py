#XXX assign to a variable to make it compatible with stickytape
DOCOPT = """
pysh -- Python for shell scripting

Usage:
  pysh [options]
  pysh [options] [--] <file>
  pysh [options] -c CODE
  pysh -h|--help
  pysh --version

Options:
  --bangexprs             Enables ! expressions.
  -c --command CODE       Run the given code with auto imports.
  -h --help               Show this screen.
  -v --verbose            Enables verbose mode.
  --version               Show version.
"""
import sys

import platform
from docopt import docopt

import pysh


# setup.py entrypoint will call this directly
def main(argv=None):
    #TODO: is this expensive? if so we can handle the version on-demand
    version = '{} ({} {} - {} {})'.format(
        pysh.__version__,
        platform.python_implementation(),
        platform.python_version(),
        platform.system(),
        platform.machine())

    args = docopt(DOCOPT, version=version, argv=argv)
    # print(args)

    if args['--command'] is not None:
        #TODO: Handle errors properly
        from pysh.command_mode import execute_and_exit
        execute_and_exit(args['--command'])


# needed for `python -m pysh` to work
if __name__ == '__main__':
    main()
