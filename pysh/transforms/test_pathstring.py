import pytest

from pysh.transforms import pathstring, testutils

lex, parse, comp, auto = testutils.factory(pathstring)


def test_lexer():
    assert lex(r'_"/usr/bin"') == r'_[r"/usr/bin"]'
    assert lex(r'_"""c:\windows"""') == r'_[r"""c:\windows"""]'
    assert lex(r'_"*.jpg"') == r'_[r"*.jpg"]'

