import os
import pytest

from pysh.path import Path


def test_relative():
    p = Path('.')
    assert str(p) == '.'
    assert str(p.resolve()) == os.path.realpath('.')

def test_dsl_sanity():
    p = Path('.')
    q = p / 'f/o/o'

    assert str(p) == '.'
    assert type(q) == Path
    assert str(q) == 'f/o/o'
    assert len(q.parents) == 3

@pytest.mark.skip(reason="globs not implemented yet")
def test_dsl_glob():
    p = Path('.')
    q = p // '*.dummy'

    assert p is not q
    assert list(q) == []

def test_dsl_anchors():
    p = Path()

    assert str(p['.']) == '.'
    assert str(p['~'].expanduser()) == os.path.expanduser('~')
    assert str(p['/']) == '/'

def test_str_eq():
    p = Path()

    assert Path('.') == '.'
    #assert Path('/foo/bar/..') == '/foo'
    #assert Path('~/foo') == os.path.expanduser('~/foo')

