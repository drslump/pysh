import sys
import os
from pathlib import Path

#TODO: alternative that uses python modules? look in script dir without X_OK?
def find_commands(prefix=None):
    commands = []

    pattern = '{}-*'.format(prefix)
    paths = [Path(p) for p in os.get_exec_path()]
    for path in paths:
        for match in path.glob(pattern):
            if os.access(match, os.X_OK):
                commands.append(match)

    print(commands)


commands = find_commands('git')
# for each command run with --help
# get the first line as command description
#

