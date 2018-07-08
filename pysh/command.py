import re
from collections import Iterable

import six


class Command:
    __slots__ = ('command', 'hyphenate', 'shortpre', 'longpre', 'valuepre', 'falsepre', 'argspre')

    def __init__(
        self, command, hyphenate=True,
        shortpre='-', longpre='--', valuepre=None, falsepre=None, argspre=None
        ):
        self.command = command
        self.hyphenate = hyphenate
        self.shortpre = shortpre
        self.longpre = longpre
        self.valuepre = valuepre
        self.falsepre = falsepre
        self.argspre = argspre

    def __repr__(self):
        return 'Command({})'.format(self.command)

    ### the following methods are proxies for invokations

    def pipe(self, *args, **kwargs):
        return CommandInvokation(self).pipe(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return CommandInvokation(self).invoke(*args, **kwargs)

    def catch(self, *args, **kwargs):
        return CommandInvokation(self).catch(*args, **kwargs)

    def to_exitcode(self):
        return CommandInvokation(self).to_exitcode()

    def to_binary(self):
        return CommandInvokation(self).to_binary()

    def to_text(self):
        return CommandInvokation(self).to_text()

    def __getitem__(self, key):
        ci = CommandInvokation(self)
        return ci[key]

    def __call__(self, *args, **kwargs):
        ci = CommandInvokation(self)
        return ci(*args, **kwargs)

    def __or__(self, other):
        return CommandInvokation(self).__or__(other)

    def __invert__(self):
        return CommandInvokation(self).__invert__()

    def __neg__(self, other):
        return CommandInvokation(self).__neg__(other)

    def __pos__(self, other):
        return CommandInvokation(self).__pos__(other)

    def __xor__(self, other):
        return CommandInvokation(self).__xor__(other)

    def __int__(self):
        return self.to_exitcode()

    if six.PY2:
        def __str__(self):
            return self.to_binary()

        def __unicode__(self):
            return self.to_text()
    else:
        def __bytes__():
            return self.to_binary()

        def __str__(self):
            return self.to_text()


class CommandInvokation:

    __slots__ = ('command', 'args', 'flags', 'no_raise', 'exitcode')

    def __init__(self, command):
        self.command = command
        self.args = []

        self.flags = set()
        self.no_raise = [0]

        self.exitcode = None

    def __copy__(self):
        """ On copy we don't carry over state, just the configuration
        """
        new = type(self)(self.command)
        new.args = list(self.args)
        new.flags = set(self.flags)
        new.no_raise = list(self.no_raise)
        return new

    def __repr__(self):
        return '<{} {}>'.format(self.command, ' '.join(self.args))

    def __getitem__(self, key):
        """ Slice access records arguments almost in verbatim form, however
            there is splitting on whitespace so if you want to pass an argument
            containing whitespace it needs to be escaped with `\`.
        """
        if isinstance(key, slice):
            raise NotImplementedError()

        args = re.split(r'(?<!\\)\s', key)
        for arg in args:
            if arg == '' or arg.isspace():
                continue
            arg = re.sub(r'\\(\s)', r'\1', arg)
            self.args.append(arg)

        return self

    def __call__(self, *args, **kwargs):
        """ Parses arguments according to:

            - single char params get a `-` prefix (`shortpre`)
            - multi char params get a `--` prefix (`longpre`)
            - snake_case params get hyphenated unless `hyphenate` is unset
            - False params are ignored unless `falsepre` is defined
            - named params always go before positional ones
            - when `argspre` is set it's used before positional arguments
            - param values are an addition arg unless `valuepre` is set
            - iterables get automatically expanded, repeating params if applies
        """

        # TODO: move most of the logic to `Command` so it can be customized there

        cmd = self.command
        for k in sorted(kwargs.keys()):
            v = kwargs[k]

            if cmd.hyphenate:
                k = re.sub(r'([A-Za-z0-9])_([A-Za-z0-9])', r'\1-\2', k)

            if isinstance(v, str) or not isinstance(v, Iterable):
                v = [v]

            #TODO: mode that doesn't repeat param name for iterables
            for value in v:
                # short params
                if len(k) == 1:
                    arg = cmd.shortpre + k
                    if value is True or value is None:
                        self.args.append(arg)
                    elif value is not False:
                        if cmd.valuepre:
                            self.args.append(arg + cmd.valuepre + str(value))
                        else:
                            self.args.append(arg)
                            self.args.append(str(value))
                # long params
                else:
                    arg = cmd.longpre + k
                    if value is True or value is None:
                        self.args.append(arg)
                    elif value is False:
                        if cmd.falsepre:
                            self.args.append(cmd.falsepre + k)
                    else:
                        if cmd.valuepre:
                            self.args.append(arg + cmd.valuepre + str(value))
                        else:
                            self.args.append(arg)
                            self.args.append(str(value))

        if cmd.argspre:
            self.args.append(cmd.argspre)

        for arg in args:
            if isinstance(arg, six.string_types):
                self.args.append(arg)
            elif isinstance(v, Iterable):
                self.args.extend(str(x) for x in arg)
            else:
                self.args.append(str(arg))

        return self

    def invoke(self):
        """ Executes the command as currently configured
        """
        raise NotImplementedError()

    def pipe(self, stdout=None, stderr=None):
        raise NotImplementedError()

    def to_exitcode(self):
        self.invoke()
        return self.exitcode

    def to_binary(self):
        self.invoke()
        return six.b(self.stdout)

    def to_text(self):
        self.invoke()
        return six.u(self.stdout)

    def catch(self, *exitcodes):
        """ Avoids raising upon given exit codes. If no exitcodes are provided
            then it'll catch all of them.
        """
        if not exitcodes:
            exitcodes = list(range(256))
        self.no_raise = exitcodes

    def __invert__(self):
        """ ~cmd -> supresses all exitcodes
        """
        self.catch()
        return self

    def __pos__(self):
        """ +cmd -> merges stderr into stdout
        """
        return self.pipe(stderr=self.stdout)

    def __neg__(self):
        """ -cmd -> supresses stderr
            --cmd -> supresses stdout and stderr
        """
        if '-' in self.flags:
            return self.pipe(stdout=None)
        else:
            self.flags |= '-'
            return self.pipe(stderr=None)

    def __xor__(self, other):
        """ expr ^ expr

            Note that ^ has higher precedence over | so compound expressions
            will bound weirdly. In theory we should be able to fix the binding
            just before invoking.
        """
        raise NotImplementedError()

    def __or__(self, other):
        return self.pipe(other)

    def __int__(self):
        return self.to_exitcode()

    if six.PY2:
        def __str__(self):
            return self.to_binary()

        def __unicode__(self):
            return self.to_text()
    else:
        def __bytes__():
            return self.to_binary()

        def __str__(self):
            return self.to_text()
