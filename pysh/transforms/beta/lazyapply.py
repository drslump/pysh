"""
Converts expressions like:

>>> func <<= cat | head > null
    func << (cat | head > null)

The whole expression at the right of the operator is grouped. This allows for
callables to receive an argument without using parenthesis.


.. Warning::
    This transformation **breaks** the standard ``<<=` operator in normal
    Python code. There is **no assignament** to the operand on the left.

"""

from io import StringIO
from tokenize import NEWLINE, ENDMARKER, OP

from pysh.transforms import TokenIO


def is_term(tkn):
    if tkn.type in (NEWLINE, ENDMARKER, OP):
        if tkn.type == OP and tkn.string != ';':
            return False
        return True
    return False


def is_lazy(tkn):
    return tkn.type == OP and tkn.string == '<<='


def lexer(code: StringIO) -> StringIO:
    out = TokenIO()
    lazy = 0
    for tkn in TokenIO(code):
        if is_lazy(tkn):
            lazy += 1
            out.write_token(tkn, override='<<(')
            continue

        if lazy > 0 and is_term(tkn):
            lazy -= 1
            out.write(')')

        out.write_token(tkn)

    return out


if __name__ == '__main__':
    code = r'''func <<= cat | \
        head \
        > null ; pass
    '''

    result = lexer(StringIO(code))
    print(result.getvalue())
