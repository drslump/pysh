import os

from pysh.env import Env


def test_access_environ():
    os.environ['__TEST_FOO__'] = 'foo'

    env = Env()
    assert env['__TEST_FOO__'] == 'foo'


def test_shadow_environ():
    os.environ['__TEST_FOO__'] = 'foo'

    env = Env(__TEST_FOO__='bar')
    assert os.environ['__TEST_FOO__'] == 'foo'
    assert env['__TEST_FOO__'] == 'bar'


def test_restore_environ():
    os.environ['__TEST_FOO__'] = 'foo'

    env = Env()
    with env:
        env['__TEST_FOO__'] = 'bar'
        assert os.environ['__TEST_FOO__'] == 'bar'

    assert os.environ['__TEST_FOO__'] == 'foo'

def test_ctxmgr_apply_environ():
    env = Env()
    with env(__TEST_FOO__='bar'):
        assert os.environ['__TEST_FOO__'] == 'bar'
