import pytest

from pysh.command import command, Pipe, Piperr, Redirect
from pysh.path import PathWrapper

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
        expr = foo | PathWrapper('test.txt')

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
        expr = PathWrapper('test.txt') | foo

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
    expr = foo ^ PathWrapper('errors.log')
    assert type(expr) is Piperr
    assert type(expr.rhs) is PathWrapper

def test_cmd_piperr_str():
    expr = foo ^ 'errors.log'
    assert type(expr) is Piperr
    assert type(expr.rhs) is str   #XXX should be PathWrapper


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
    expr = foo > PathWrapper('out.txt')
    assert type(expr) is Redirect
    assert type(expr.rhs) is PathWrapper

def test_cmd_gt_str():
    expr = foo > 'out.txt'
    assert type(expr) is Redirect
    assert type(expr.rhs) is str  #XXX should be PathWrapper

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
    assert type(expr.rhs) is str  #XXX should be PathWrapper


# compound

def test_cmd_pipe_cmd_gt_file():
    expr = foo | bar > null
    assert type(expr) is Redirect
    assert type(expr.lhs) is Pipe
    assert expr.rhs is null
    assert expr.lhs.lhs is foo
    assert expr.lhs.rhs is bar

def test_cmd_piperr_file_pipe_cmd():
    expr = foo ^null | bar
    assert type(expr) is Pipe
    assert type(expr.lhs) is Piperr
    assert expr.lhs.lhs is foo
    assert expr.lhs.rhs is null
    assert expr.rhs is bar

def test_cmd_gt_file_pipe_cmd():
    with pytest.raises(TypeError):
        expr = foo >null | bar

    # pointless but should be valid?
    expr = (foo >null) | bar
    assert type(expr) is Pipe
    assert type(expr.lhs) is Redirect
    assert expr.lhs.lhs is foo
    assert expr.lhs.rhs is null
    assert expr.rhs is bar
