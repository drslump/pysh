"""
Simple lexer transform to support *path string literals*.

>>> _'*.jpg'
    _[r'*.jpg']

"""

from io import StringIO

from pysh.transforms import TokenIO, zip_prev, STARTMARKER
from tokenize import NAME, STRING


def lexer(code: StringIO) -> StringIO:
    out = TokenIO()
    for ptkn, ctkn in zip_prev(TokenIO(code), STARTMARKER):
        if ctkn.type == STRING and ptkn.type == NAME and ptkn.string == '_':
            if ctkn.start == ptkn.end:
                out.write_token(ctkn, override='[r' + ctkn.string + ']')
                continue

        out.write_token(ctkn)

    return out


if __name__ == '__main__':
    code = r'''
_'*.jpg'
_"foo/bar/*"
_'c:\windows'
    '''.strip()

    out = lexer(StringIO(code))
    print(out.getvalue())