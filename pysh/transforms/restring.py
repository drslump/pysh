"""
Simple lexer transform to support *regex string literals*.

>>> re'\w+'
    re.compile(r'\w+', re.VERBOSE)

The string handled as *raw* and the regex is parsed with the *VERBOSE* flag
enabled so white space is ignored. If you need to set another flag use the
inline syntax ``(?...)``.

"""

import re
from io import StringIO

from pysh.transforms import TokenIO, zip_prev, STARTMARKER
from tokenize import NAME, STRING

from typing import Pattern


__all__ = ['__PYSH_RESTRING__']


def is_prefix(tkn):
    return tkn.type == NAME and tkn.string == 're'


def lexer(code: StringIO) -> StringIO:
    out = TokenIO()
    for ptkn, ctkn in zip_prev(TokenIO(code), STARTMARKER):
        if is_prefix(ctkn):
            continue  # defer until next token

        if is_prefix(ptkn):
            if ctkn.type == STRING and ctkn.start == ptkn.end:
                out.write_token(ptkn, override='__PYSH_RESTRING__(r' + ctkn.string + ')')
                continue
            else:
                out.write_token(ptkn)

        out.write_token(ctkn)

    return out


def __PYSH_RESTRING__(regex: str) -> Pattern:
    return re.compile(regex, re.VERBOSE)


if __name__ == '__main__':
    code = '''
re '2'
re""".*"""
    '''.strip()

    out = lexer(StringIO(code))
    print(out.getvalue())
