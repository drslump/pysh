Preface
=======

Motivation
----------

The overall consensus is that *shell scripting* with *sh* can get messy real
quick, it's a tool that feels arcane to many programmers and while in general
it's great for instrumenting simple tasks it requires a very depth knowledge
of the tool to even understand a moderately complex script, let alone write
one with confidence.

Personally I think the main problem with using a *shell* for *shell scripting*
is that they solve two completely different problems with the same tool. On one
side they need to provide an *interactive mode* where syntax should be very terse
to be useful, while on the other they reuse that syntax and semantics for actual
*programming* tasks. Some shells like *fish* seem like a good step on solving that
problem but still focus on its primary use case of being an *interactive shell*.

Another important issue with *sh* based scripting is portability, while *bash*
is ubiquitous nowadays and is usually good enough to assume its syntax, it relies
on the *standard unix utilities* which unfortunately are not fully compatible
between systems with GNU or BSD roots, let alone Windows. This becomes obvious
when developing on *macOS* (BSD roots) but running on *Linux* (GNU roots).

Then there is *perl* and *tcl*, which should help with those problems but
unfortunately they also have an arcane feeling for many or a very limited standard
library in *tcl*'s case. Next is a myriad of *scripting* languages like *python*,
*ruby*, *php* or *lua*, that have found their sweet spots in other domains and
while capable of *shell scripting* don't offer an ergonomic solution for it.

From the scripting languages *python* crosses many t's. The most important
being its good readability even for inexperienced programmers, *bateries included*
philosophy with a very rich and portable standard library, solid packaging story
and its mixture of dynamic runtime with strong typing that makes errors more
obvious.

If we can make *python* behave a bit more like *tcl* we might have a winner.


Requeriments
------------

The **target runtime is Python 3.6** (CPython implementation) on *posix* systems.
Targeting that specific version for the *initial prototype* makes coding it more
fun, allowing to focus on solving the problems without thinking about backwards
compatibility, it also enables some interesting features like type hinting.

Once the project matures it should be possible to add support for older Python3
versions. Supporting Python2 would be much harder though and it's not planned
unless there is someone strongly motivated to do it.

As for supported operating systems the story is similar, the goal is to fully
support Linux and macOS/OSX. Supporting Windows and less popular unixes will
depend on finding a motivated contributor to implement it. That being said, the
bare basics *should* work on every system with *CPython* support.



Prior art
---------

Searching for similar software turned out quite a few options, perhaps one of
them might work best for your use case.

 - `Plumbum <https://github.com/tomerfiliba/plumbum>`_
 - `shellpy <https://github.com/lamerman/shellpy>`_
 - `Sarge <http://sarge.readthedocs.io/en/latest/>`_
 - `sh <http://amoffat.github.io/sh/>`_
 - `Delegator <https://github.com/kennethreitz/delegator.py>`_
 - `pexpect <https://github.com/pexpect/pexpect>`_
