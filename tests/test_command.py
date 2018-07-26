import pytest

from pysh.dsl.command import command
from pysh.dsl.pipeline import Command, Pipe, Piperr, Redirect, Application
from pysh.dsl.path import Path

foo = command('foo')
bar = command('bar')
null = open('/dev/null')


# pipe

def test_cmd_pipe_cmd():
    expr = foo | bar
    assert type(expr) is Pipe
    assert repr(expr) == '(`foo` | `bar`)'

def test_cmd_pipe_func():
    # not implemented yet
    with pytest.raises(TypeError):
        expr = foo | print

def test_cmd_pipe_file():
    with pytest.raises(TypeError):
        expr = foo | null

def test_cmd_pipe_path():
    with pytest.raises(TypeError):
        expr = foo | Path('test.txt')

def test_cmd_pipe_str():
    with pytest.raises(TypeError):
        expr = foo | 'test.txt'

def test_file_pipe_cmd():
    # not implemented yet
    with pytest.raises(TypeError):
        expr = null | foo

def test_path_pipe_cmd():
    # not implemented yet
    with pytest.raises(TypeError):
        expr = Path('test.txt') | foo

def test_any_pipe_cmd():
    # not implemented yet
    with pytest.raises(TypeError):
        expr = [1,2,3] | foo

# piperr

def test_cmd_piperr_cmd():
    expr = foo ^ bar
    assert type(expr) is Piperr
    assert repr(expr) == '(`foo` ^ `bar`)'

def test_cmd_piperr_file():
    expr = foo ^ null
    assert type(expr) is Piperr
    assert type(expr.rhs) is type(null)

def test_cmd_piperr_path():
    expr = foo ^ Path('errors.log')
    assert type(expr) is Piperr
    assert type(expr.rhs) is Path

def test_cmd_piperr_str():
    expr = foo ^ 'errors.log'
    assert type(expr) is Piperr
    assert type(expr.rhs) is str   #XXX should be Path


# redirect

def test_cmd_gt_file():
    expr = foo > null
    assert type(expr) is Redirect
    assert type(expr.rhs) is type(null)
    assert repr(expr) == '(`foo` > /dev/null)'

def test_cmd_gt_cmd():
    with pytest.raises(TypeError):
        expr = foo > bar

def test_cmd_gt_path():
    expr = foo > Path('out.txt')
    assert type(expr) is Redirect
    assert type(expr.rhs) is Path

def test_cmd_gt_str():
    expr = foo > 'out.txt'
    assert type(expr) is Redirect
    assert type(expr.rhs) is str  #XXX should be Path

def test_cmd_gt_int():
    with pytest.raises(TypeError):
        expr = foo > 10

def test_cmd_gt_func():
    # not implemented yet
    with pytest.raises(TypeError):
        expr = foo > print

def test_file_lt_cmd():
    expr = null < foo
    assert type(expr) is Redirect
    assert type(expr.rhs) is type(null)
    assert repr(expr) == '(`foo` > /dev/null)'

def test_str_lt_cmd():
    expr = 'out.txt' < foo
    assert type(expr) is Redirect
    assert type(expr.rhs) is str  #XXX should be Path


# reckless

def test_tilde_cmd():
    expr = ~foo
    assert expr.reckless is True
    assert type(expr) is Command

def test_tilde_tilde_cmd():
    expr = ~~foo
    assert expr.reckless is False
    assert type(expr) is Command

def test_tilde_cmd_arg():
    expr = ~foo('fname')
    assert expr.reckless is True
    assert type(expr) is Command

    expr = ~foo['fname']
    assert expr.reckless is True
    assert type(expr) is Command

def test_tilde_pipe():
    expr = ~(foo | bar)
    assert expr.reckless is True
    assert type(expr) is Pipe

def test_tilde_redirect():
    expr = ~foo > 'out.txt'
    assert type(expr) is Redirect
    assert expr.reckless is False
    assert type(expr.lhs) is Command
    assert expr.lhs.reckless is True


# compound

def test_cmd_pipe_cmd_gt_file():
    expr = foo | bar > null
    assert type(expr) is Redirect
    assert type(expr.lhs) is Pipe
    lhs, rhs = expr.lhs, expr.rhs
    assert lhs.lhs is foo
    assert lhs.rhs is bar
    assert rhs is null

def test_cmd_piperr_file_pipe_cmd():
    expr = foo ^null | bar
    assert type(expr) is Pipe
    assert type(expr.lhs) is Piperr
    lhs, rhs = expr.lhs, expr.rhs
    assert lhs.lhs is foo
    assert lhs.rhs is null
    assert rhs is bar

def test_cmd_gt_file_pipe_cmd():
    with pytest.raises(TypeError):
        expr = foo >null | bar

    # pointless but should be valid?
    expr = (foo >null) | bar
    assert type(expr) is Pipe
    assert type(expr.lhs) is Redirect
    lhs, rhs = expr.lhs, expr.rhs
    assert lhs.lhs is foo
    assert lhs.rhs is null
    assert rhs is bar


# application operator

def test_cmd_lshift_cmd():
    expr = foo << bar
    assert type(expr) is Command
    assert len(expr.args) == 1  #TODO: check it's `bar`

def test_func_lshift_cmd():
    capture = []
    capture.append << foo
    assert capture == [foo]

def test_cmd_lshift_redirect():
    expr = foo << bar > null
    assert type(expr) is Redirect
    assert type(expr.lhs) is Command
    assert len(expr.lhs.args) == 1  #TODO: check it's `bar`
    assert expr.rhs is null
