# Pattern matching in Python without transformations

import operator


class Capture:
    def __init__(self, name):
        self.name = name
        self.iter = False

    def __iter__(self):
        self.iter = True
        yield self


class Match:

    @staticmethod
    def lt(cls, other):
        return lambda x: operator.lt(x, other)

    @staticmethod
    def le(cls, other):
        return lambda x: operator.le(x, other)

    @staticmethod
    def eq(cls, other):
        return lambda x: operator.eq(x, other)

    @staticmethod
    def ne(cls, other):
        return lambda x: operator.ne(x, other)

    @staticmethod
    def gt(cls, other):
        return lambda x: operator.gt(x, other)

    @staticmethod
    def ge(cls, other):
        return lambda x: operator.ge(x, other)

    @staticmethod
    def contains(cls, other):
        return lambda x: operator.contains(other, x)

    def __init__(self, subject):
        self.subject = subject
        self.matched = False

    def match(self):
        self.matched = True

    def unmatch(self):
        self.matched = False

    def __getattr__(self, name):
        return Capture(name)

    def __call__(self, pattern=..., **kwargs):
        """
        - []: sequence
        - (): union
        - {k:v}: mapping/attributes
        - {set}: tests all exists as key,attr or items (in order)
        - keyword args: same as {k:v}
        - type, xxx: match type then compare structure
        - callable: check return value
        - other: match equality

        - m.X capture
        - *m.X capturing wildcard for sequences
        - ... matches anything and wildcard for sequences
        - m.X(pattern) captures if matches
        """
        #TODO: find a way to clean previous captures

        if self.matched:
            return False

        if isinstance(pattern, type):
            if not isinstance(self.subject, pattern):
                return False
        elif kwargs:
            for k, v in kwargs.items():
                if hasattr(self._subject, k):
                    setattr(self, v.name, getattr(self._subject, k))
                else:
                    return False

        self.matched = True
        return self

    def __gt__(self, rhs):
        if self.matched:
            return self

        return self(rhs)

    def __eq__(self, rhs):
        if self.matched:
            return self

        return self(rhs)

    def __getitem__(self, item):
        """
        Shortcut for unions
        """
        if type(item) == slice:
            raise TypeError('Unsupported slice syntax')

        # item is already a tuple if mutiple are given
        return self(item)

    def __bool__(self):
        if self.matched:
            return False

        self.matched = True
        return True

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_tb):
        if not self.matched:
            raise RuntimeError('Unexhaustive match')

        #TODO: Clean all references

    def __del__(self):
        #TODO: clean all references
        pass


import json
messages = json.loads('''
    [
        {"name": {"first": "Mary", "last": "Higgins"}, "age": 28},
        {"creator": "God", "uptime": 1043223}
    ]
    ''')

for msg in messages:
    with Match(foo) as m:
        if m(name={'first': m.firstname}, age=m.age):
            print('User {} is {} years old'.format(m.firstname, m.age))

        if m(creator=..., uptime=m.seconds(int)):
            print('Bot has been rocking for {} seconds!'.format(m.seconds))

        if m:  # else clause, if not set and no match found it would error
            print('Unknown message: {!r}'.format(m.subject))

    # not to far off from some possible syntax if it was natively supported
    match foo:
        case dict(name=dict(first=firstname), age=age):
            print('User {} is {} years old'.format(firstname, age))

        case dict(creator=_, uptime=int(seconds)):
            print('Bot has been rocking for {} seconds!'.format(seconds))

        default:
            print('Unknown message: {!r}'.format(foo))

# Slice serves to check a type and also for alternates
m = Match(foo)
if m[
    m[dict](name={'first': m.name}),
    m[dict](name=m.name)
    ]:
    print('Name is {}'.format(m.name))







foo = 10

with Match(foo) as m:  # with context manager matching must be exhaustive
    if m(attrib=m.a)        : print('foo.attrib', m.a)
    if m(int)               : print('type is int:', m.subject)
    if m> int> m.a          : print('type is int:', m.a)
    if m> m.a(int)          : print('type is int:', m.a)

    if m.i(int) or m.s(str)    : print('int or str')
    # using `and` is risky because it calls __bool__ and we use it to
    # determine if a match branch was succesful to determine exhaustiveness.
    # Besides, boolean ops are eagerly computed so they can be used in nested
    # structures.
    if m(attrib=m.a) and m.a > 10: print('capture and compare')
    if m(attrib=m.a) and m.a < 10: print('will not work because matched already')
    # when not using elif we can manually unmatch
    if m(attrib=m.a):
        if m.a > 10:
            m.unmatch()
        else:
            pass
    # using a curried comparison (callable)
    if m(attrib=m.a(Match.gt(10)))      : print('attrib > 10')

    # another option would be to use methods but it's really ugly
    if m(attrib=m.a).and_then(lambda: m.a > 10): pass
    if m(attrib=m.a).or_else(lambda: m.a > 10): pass

    if m({
        'foo': m.a,
        'bar': [*m.head, m, *m.tail],   # m is simply ignored
        'baz': [..., m.a(int)]  # captures can also match nested values
        })                  : print('foo["foo"]', m.a)
    if m([m._, m.a, m.b, ...])     : print('foo[]', m.a, m.b)
    if m> [*m.head, m._]      : print('foo[]', m.extra)
    # shortcut for unions
    if m[int, str, bytes]    : print('foo union')
    if m == (int, str, bytes)    : print('foo union')
    if m                    : print('else')


m = match(foo)
if m(attrib=m.a)    : print('foo.attrib', m.a)
if m(int)           : print('type is int', m.subject)
# no exhaustive check without a `with`


# Also a decorator for multimethods

@match(foo=int)
def multimethod(foo):
    print('foo is an int')

@match(foo=str)
def multimethod(foo):
    print('foo is a str')

@match  # uses type hints
def multimethod(foo: bool):
    print('foo is a bool')

@match(foo={'prop': match.prop})
def multimethod(prop):
    print('captures are supported too')
