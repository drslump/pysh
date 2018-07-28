import os
import re
import pytest

from pysh.dsl import Path, \
    PathMatcher, GlobMatcher, RegexMatcher, FilterMatcher, RecursiveMatcher


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

def test_dsl_glob():
    p = Path('.')
    q = p // '*.cfg'

    assert p is not q
    assert type(q) == GlobMatcher
    assert list(q.iter_posix()) == ['./setup.cfg']

def test_dsl_regex():
    p = Path('.')
    q = p // re.compile(r'setup\.(py|cfg)')

    assert type(q) == RegexMatcher
    assert sorted(q.iter_posix()) == ['./setup.cfg', './setup.py']

    q = p // re.compile(r'setup\.p')  # no partial matches
    assert sorted(q.iter_posix()) == []

def test_dsl_callable():
    fn = lambda p: p.is_dir() and p.name == 'pysh'
    p = Path('.')
    q = p // fn

    assert type(q) == FilterMatcher
    assert sorted(q.iter_posix()) == ['./pysh']

def test_dsl_recursive():
    p = Path('./pysh')  # make the test faster :)
    q = p ** 'precedence.py'
    assert sorted(q.iter_posix()) == ['pysh/transforms/precedence.py']

    q = p ** 'transforms/precede*.py'
    assert sorted(q.iter_posix()) == ['pysh/transforms/precedence.py']

    q = p ** re.compile(r'pr[ecd]+nce.py')
    assert sorted(q.iter_posix()) == ['pysh/transforms/precedence.py']

    fn = lambda p: p.is_file() and p.name == 'precedence.py'
    q = p ** fn
    assert sorted(q.iter_posix()) == ['pysh/transforms/precedence.py']

def test_dsl_glob_expansion():
    p = Path('.')
    q = p // 'setu?.{cfg,py}'

    assert sorted(q.iter_posix()) == ['./setup.cfg', './setup.py']

def test_dsl_glob_paths():
    p = Path('.')
    q = p // 'setup.py'

    files = sorted(q)
    assert len(files) == 1
    assert type(files[0]) == Path
    assert files[0].as_posix() == 'setup.py'

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

def test_bool_cast():
    p = Path() / 'setup.py'
    if not p:
        assert False, 'Path should evaluate to True if exists'

    p = Path() / 'not-exists.dummy'
    if p:
        assert False, 'Path should evaluate to False if not exists'
