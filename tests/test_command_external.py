
import pytest

from pysh.command import ExternalSpec
from pysh.dsl import Command


def test_args_short():
    spec = ExternalSpec('cmd')
    c = Command(spec)(a=True, b=True, c=False, d=10)
    args = spec.get_args_for(c)
    assert args == ['-a', '-b', '-d', '10']

def test_args_hyphenate():
    spec = ExternalSpec('cmd')
    c = Command(spec)('bar', opt_bool=True, opt_str='str', opt_multi=[1,2])
    args = spec.get_args_for(c)
    assert  ' '.join(args) \
        == '--opt-bool --opt-str str --opt-multi 1 --opt-multi 2 bar'

def test_args_valuepre():
    spec = ExternalSpec('cmd', valuepre='=')
    c = Command(spec)
    args = spec.get_args_for(c(opt=1))
    assert ' '.join(args) == '--opt=1'
    args = spec.get_args_for(c(opt=[1,2]))
    assert ' '.join(args) == '--opt=1 --opt=2'

def test_args_argspre():
    spec = ExternalSpec('cmd', argspre='--')
    c = Command(spec)
    assert spec.get_args_for( c('bar', 'baz', opt=True) ) == ['--opt', '--', 'bar', 'baz']
    assert spec.get_args_for( c('foo', 'bar') ) == ['--', 'foo', 'bar']

def test_args_slice():
    spec = ExternalSpec('cmd')
    c = Command(spec)
    assert spec.get_args_for(c['foo']) == ['foo']
    assert spec.get_args_for(c['foo bar']) == ['foo', 'bar']
    assert spec.get_args_for(c[r'foo\ bar']) == ['foo bar']
    assert spec.get_args_for(c[r'foo\ \ bar']) == ['foo  bar']
    assert spec.get_args_for(c['foo\\\tbar']) == ['foo\tbar']

def test_args_repeat():
    spec = ExternalSpec('cmd', repeat=',')
    c = Command(spec)
    assert spec.get_args_for(c(opt=[1,2,3])) == ['--opt', '1,2,3']

    spec = ExternalSpec('cmd', repeat=',', valuepre='=')
    c = Command(spec)
    assert spec.get_args_for(c(opt=[1,2,3])) == ['--opt=1,2,3']

def test_args_underscore_positional():
    spec = ExternalSpec('cmd')
    c = Command(spec)
    assert spec.get_args_for(c(opt=True, _='foo')) == ['--opt', 'foo']
    assert spec.get_args_for(c('bar', opt=True, _='foo')) == ['--opt', 'bar', 'foo']
    assert spec.get_args_for(c(opt=True, _=['foo', 'bar'])) == ['--opt', 'foo', 'bar']

def test_args_attr():
    spec = ExternalSpec('cmd')
    c = Command(spec)
    assert spec.get_args_for(c.a) == ['-a']
    assert spec.get_args_for(c.a.b.c) == ['-a', '-b', '-c']
    assert spec.get_args_for(c.a.b.c(10)) == ['-a', '-b', '-c', '10']
    assert spec.get_args_for(c.long) == ['--long']
    assert spec.get_args_for(c.long(10)) == ['--long', '10']
    assert spec.get_args_for(c.a.long.b) == ['-a', '--long', '-b']
    assert spec.get_args_for(c.hyphe_nate) == ['--hyphe-nate']

    with pytest.raises(AttributeError):
        c._foo  # underscode attributes are reserved
