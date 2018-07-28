"""
Simple lexer transform to support *path string literals*.

>>> _'*.jpg'
    _[r'*.jpg']

"""

from io import StringIO

from pysh.transforms import TokenIO, zip_prev, STARTMARKER
from tokenize import TokenInfo, NAME, STRING


def lexer(code: StringIO) -> StringIO:
    out = TokenIO()
    tokens = TokenIO(code).iter_tokens()
    for ptkn, ctkn in zip_prev(tokens, STARTMARKER):
        assert isinstance(ptkn, TokenInfo)  #XXX Mypy stuff

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