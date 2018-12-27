
import pytest

from pysh.command import ExternalSpec
from pysh.dsl import Command


cmd = Command(ExternalSpec('dummy'))

def args(cmd, **kwargs):
    spec = ExternalSpec(cmd, **kwargs)
    return spec.get_args_for(cmd)


def test_args_short():
    c = cmd(a=True, b=True, c=False, d=10)
    assert args(c) == ['-a', '-b', '-d', '10']

def test_args_hyphenate():
    c = cmd('bar', o_bool=True, o_str='str', o_multi=[1,2])
    assert args(c) == ['--o-bool', '--o-str', 'str', '--o-multi', '1', '--o-multi', '2', 'bar']

def test_args_valuepre():
    c = cmd(opt=1)
    assert args(c, value='=') == ['--opt=1']
    c = cmd(opt=[1,2])
    assert args(c, value='=') == ['--opt=1', '--opt=2']

def test_args_argspre():
    assert args(
            cmd('bar', 'baz', opt=True),
            args='--'
        ) == [
            '--opt', 'bar', 'baz'
        ], 'no argspre if not needed'

    assert args(
            cmd('bar', '-baz', opt=True),
            args='--'
        ) == [
            '--opt', '--', 'bar', '-baz'
        ], 'argspre shows before run of args that require it'

    assert args(
            cmd(opt=True, _=['bar', '-baz']),
            args='--'
        ) == [
            '--opt', '--', 'bar', '-baz'
        ], 'argspre shows before run of args that require it'

    assert args(
            cmd('foo', '-bar'),
            args='--'
        ) == [
            '--', 'foo', '-bar'
        ], 'argspre shows even if no keywords are set'

    assert args(
            cmd('+foo', opt=True)('+bar', opt=True),
            args='++',
            long='+'
        ) == [
            '+opt', '++', '+foo', '+opt', '+bar'
        ], 'argspre supports arbitrary flags'

    assert args(
            cmd('-foo'),
            args='++',
            short='+',
            long='++'
        ) == [
            '-foo'
        ], 'argspre supports arbitrary flags'

    assert args(
            cmd['--'](opt=True)('--bar'),
            args='--'
        ) == [
            '--', '--opt', '--bar'
        ], 'respect if argspre was explicitly added'

def test_args_slice():
    assert args(cmd['foo']) == ['foo']
    assert args(cmd['foo bar']) == ['foo', 'bar']
    assert args(cmd[r'foo\ bar']) == ['foo bar']
    assert args(cmd[r'foo\ \ bar']) == ['foo  bar']
    assert args(cmd['foo\\\tbar']) == ['foo\tbar']

def test_args_repeat():
    assert args(
        cmd(opt=[1,2,3]),
        repeat=True  # default
        ) == ['--opt', '1', '--opt', '2', '--opt', '3']

    assert args(
        cmd(opt=[1,2,3]),
        repeat=False,
        ) == ['--opt', '1', '2', '3']

    assert args(
        cmd(opt=[1,2,3]),
        repeat=','
        ) == ['--opt', '1,2,3']

    assert args(
        cmd(opt=[1,2,3]),
        repeat=',',
        value='='
        ) == ['--opt=1,2,3']



def test_args_underscore_positional():
    assert args(cmd(opt=True, _='foo')) == ['--opt', 'foo']
    assert args(cmd('bar', opt=True, _='foo')) == ['--opt', 'bar', 'foo']
    assert args(cmd(opt=True, _=['foo', 'bar'])) == ['--opt', 'foo', 'bar']

def test_args_attr():
    assert args(cmd.a) == ['-a']
    assert args(cmd.a.b.c) == ['-a', '-b', '-c']
    assert args(cmd.a.b.c(10)) == ['-a', '-b', '-c', '10']
    assert args(cmd.long) == ['--long']
    assert args(cmd.long(10)) == ['--long', '10']
    assert args(cmd.a.long.b) == ['-a', '--long', '-b']
    assert args(cmd.hyphe_nate) == ['--hyphe-nate']

    with pytest.raises(AttributeError):
        cmd._foo  # underscode attributes are reserved
