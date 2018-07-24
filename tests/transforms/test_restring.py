import pytest

from pysh.transforms import restring

from .utils import factory, lex, parse, comp

lex, parse, comp, auto = factory(restring)


def test_lexer():
    assert lex(r're"\w+"') == r'__PYSH_RESTRING__(r"\w+")'
    assert lex(r're"""\w+"""') == r'__PYSH_RESTRING__(r"""\w+""")'
    assert lex(r're "\w+"') == r're "\w+"'


def test_regex_verbose():
    expr = auto(r're"\w+ \d+"')

    assert hasattr(expr, 'match')
    assert expr.match('abc123')
    assert not expr.match('abc 123')

