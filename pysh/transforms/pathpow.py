"""
Allows to use the ``**`` operator in a chained path expresion.


.. Caution::
    This transformation applies to all the ``**`` operators in the code,
    it's designed to work transparently when the left hand side operand is
    not a *str*, a *regex* or a *callable* but it could introduce issues if
    the operator is used profusely or mixing it with classes that implement
    its overload.


Since ``**`` has a higher binding precedence than ``/`` or ``//``, it won't
evaluate as expected when we have something like:

>>> _ / 'subdir' ** '*.jpg'
  # _ / ('subdir' ** '*.jpg')  # TypeError: pow not defined for str

With this transform all the ``**`` operators in the script are modified as to
generate a *GlobRecursive* instance when the left hand side operand is a *str*,
a *regex* or a *callable*.

>>> _ / 'subdir' ** '*.jpg'
    _ / 'subdir' **__PYSH_POW__** '*.jpg'       # lexer transform
    _ / GlobRecursive('subdir', '*.jpg')        # evaluation

>>> 1 ** 2 ** 3
    1 **__PYSH_POW__** 2 **__PYSH_POW__** 3     # lexer transform
    1 ** (2 ** 3)                               # evaluation

"""

from io import StringIO
from tokenize import OP, DOUBLESTAR, COMMA, LPAR, NAME
from pathlib import PurePath

from pysh.transforms import TokenIO, zip_prev, STARTMARKER
from pysh.dsl import Path, RecursiveMatcher


__all__ = ['__PYSH_POW__']


class PowResolver:

    def __pow__(self, rhs, modulo=None):
        self.rhs = rhs
        return self

    def __rpow__(self, lhs):
        if isinstance(lhs, (str, PurePath)):
            return RecursiveMatcher(Path(lhs), self.rhs)

        return lhs ** self.rhs


__PYSH_POW__ = PowResolver()


def is_pow(ptkn, ctkn):
    return ctkn.exact_type == DOUBLESTAR \
       and ptkn.exact_type not in (COMMA, LPAR) \
       and not (ptkn.type == NAME and ptkn.string == 'lambda')


def lexer(code: StringIO, *, fname:str=None) -> StringIO:
    out = TokenIO()
    for ptkn, ctkn in zip_prev(TokenIO(code), STARTMARKER):
        if is_pow(ptkn, ctkn):
            out.write_token(ctkn, override='**__PYSH_POW__**')
        else:
            out.write_token(ctkn)

    return out
