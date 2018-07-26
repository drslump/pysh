from functools import partial
import pytest

from pysh.transforms import shadowing

from .utils import factory


lex, parse, comp, auto = factory(shadowing)


def test_assignment():
    with pytest.warns(SyntaxWarning):
        comp('_ = 10')

def test_inplace():
    with pytest.warns(SyntaxWarning):
        comp('_ += 10')

def test_assign_in_function():
    with pytest.warns(SyntaxWarning):
        comp('''\
            def foo():
                _ = 10
        ''')

def test_assign_in_loop():
    with pytest.warns(SyntaxWarning):
        comp('for _ in range(5): pass')

def test_with():
    with pytest.warns(SyntaxWarning):
        comp('''\
            with open('file.txt') as _:
                pass
        ''')
