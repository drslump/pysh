from functools import partial
import pytest

from pysh.transforms import pathpow
from pysh.path import Path, GlobRecursive

from .utils import factory

lex, parse, comp, auto = factory(pathpow)


def test_rglob():
    assert lex('_ ** g') == '_ **__PYSH_POW__** g'


def test_rglob_dsl():
    expr = auto("_ ** 'foo'")

    assert type(expr) == GlobRecursive
    assert expr.pattern == 'foo'


def test_rglob_precendence():
    expr = auto("_ / 'foo' ** '*.jpg'")

    assert type(expr) == GlobRecursive
    assert expr.path == 'foo'


def test_rglob_callable():
    expr = auto("_ / str.isalpha ** '*.jpg'")

    assert type(expr) == GlobRecursive
    assert expr.path == str.isalpha


@pytest.mark.parametrize("expression", [
    ('2**3'),
    ('2**-3'),
    ('2**3**4'),
    ('2**2 / 2**2'),
    ('2**2+3'),
    ('2**2*3'),
    ('2*3**4'),
])
def test_arithmetic(expression):
    assert auto(expression) == eval(expression)
