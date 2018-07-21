import os
import pytest

from pysh.path import PathWrapper


def test_relative():
    p = PathWrapper('.')
    assert str(p) == '.'
    assert str(p.resolve()) == os.path.realpath('.')

def test_dsl_sanity():
    p = PathWrapper('.')
    q = p / 'f/o/o'

    assert str(p) == '.'
    assert type(q) == PathWrapper
    assert str(q) == 'f/o/o'
    assert len(q.parents) == 3

@pytest.mark.skip(reason="globs not implemented yet")
def test_dsl_glob():
    p = PathWrapper('.')
    q = p // '*.dummy'

    assert p is not q
    assert list(q) == []

def test_dsl_anchors():
    p = PathWrapper()

    assert str(p['.']) == '.'
    assert str(p['~'].expanduser()) == os.path.expanduser('~')
    assert str(p['/']) == '/'

def test_str_eq():
    p = PathWrapper()

    assert PathWrapper('.') == '.'
    #assert PathWrapper('/foo/bar/..') == '/foo'
    #assert PathWrapper('~/foo') == os.path.expanduser('~/foo')

