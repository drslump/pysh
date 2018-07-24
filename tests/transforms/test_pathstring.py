import pytest

from pysh.transforms import pathstring

from .utils import factory

lex, parse, comp, auto = factory(pathstring)


def test_lexer():
    assert lex(r'_"/usr/bin"') == r'_[r"/usr/bin"]'
    assert lex(r'_"""c:\windows"""') == r'_[r"""c:\windows"""]'
    assert lex(r'_"*.jpg"') == r'_[r"*.jpg"]'

