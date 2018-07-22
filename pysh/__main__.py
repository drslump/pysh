"""
pysh %version% -- Python for shell scripting

Usage:
  %program% [options] [--transform MODULE]... [--] [FILE]
  %program% [options] -e CODE
  %program% -h|--help [SYMBOL]
  %program% --version

Options:
  --transform MODULE      Enables a source code transform.
  -e --eval CODE          Eval the given code with auto imports.
  -h --help               Show this screen or help for a symbol.
  -v --verbose            Enables verbose mode.
  --debug                 Enables debug mode.
  --quiet                 Enables quiet mode.
  --version               Show version.
"""
import sys
import re
import platform
import logging
from pathlib import PurePath

from docopt import docopt

import pysh

#TODO: pysh should understand metadata variables and allow to interpolate
#      them in the docopt. Also use them for packaging.
# __author__ = "Rob Knight, Gavin Huttley, and Peter Maxwell"
# __copyright__ = "Copyright 2007, The Cogent Project"
# __credits__ = ["Rob Knight", "Peter Maxwell", "Gavin Huttley",
#                     "Matthew Wakefield"]
# __license__ = "GPL"
# __version__ = "1.0.1"
# __maintainer__ = "Rob Knight"
# __email__ = "rob@spot.colorado.edu"
# __status__ = "Production"


SCRIPT_TRANSFORMS = [
    'pysh.transforms.autoexpr',
    'pysh.transforms.protectnames',
]

EVAL_TRANSFORMS = [
    'pysh.transforms.autoimport',
    'pysh.transforms.autoreturn',
]

# Start logs in default level
logging.basicConfig(level=logging.WARN)


def eval_and_exit(code: str):
    """ Execute the code and exit according to the last expression:
        - False: exitcode 1
        - True/None: exitcode 0
        - Else: print it and exitcode 0
    """
    from io import StringIO
    from pysh.transforms import Compiler

    compiler = Compiler(EVAL_TRANSFORMS)

    fn = compiler.compile(StringIO(code), 'pysh-eval')

    try:
        result = fn()
    except Exception as ex:
        print('{}: {}'.format(ex.__class__.__name__, ex), file=sys.stderr)
        raise SystemExit(3)

    if result is False:
        raise SystemExit(1)

    if result is not True and result is not None:
        print('{}'.format(result))

    raise SystemExit(0)


# setup.py entrypoint will call this directly
def main(argv=None):
    version = '{} ({} {} - {} {})'.format(
        pysh.__version__,
        platform.python_implementation(),
        platform.python_version(),
        platform.system(),
        platform.machine())

    #TODO: When compiling code from stdin a traceback won't show the lines
    #      since Python cannot open stdin again. We should investigate if
    #      we can keep a copy around and use it for tracebacks.

    #TODO: `--transform foo --transform bar` yields ['foo', 'bar', 'bar']
    opts = dict(version=pysh.__version__, program=PurePath(sys.argv[0]).name)
    doc = re.sub(r'%([A-Za-z_]+)%', lambda m: opts[m.group(1)], __doc__)
    args = docopt(doc, help=False, version=version, argv=argv)
    # print(args)

    if args['--help']:
        symbol = args['SYMBOL']
        if symbol:
            if symbol not in pysh.__dict__:
                print('Unknown symbol {}'.format(symbol), file=sys.stderr)
                raise SystemExit(1)

            help(pysh.__dict__[symbol])
        else:
            print(doc, file=sys.stderr)

        raise SystemExit(0)


    # Tune log level based on flags
    if args['--verbose']:
        logging.getLogger('').setLevel(logging.INFO)
    elif args['--debug']:
        logging.getLogger('').setLevel(logging.DEBUG)
    elif args['--quiet']:
        logging.getLogger('').setLevel(logging.CRITICAL)

    if args['--eval'] is not None:
        eval_and_exit(args['--eval'])


# needed for `python -m pysh` to work
if __name__ == '__main__':
    main()
