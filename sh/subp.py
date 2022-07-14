#! /usr/bin/env python3

import atexit
import os
import re
import shutil
import subprocess as sp
import typing as T

from tabulate import tabulate

from .. import cmd


# typedef

ProcMap = T.NewType('ProcMap', T.Mapping[int, sp.Popen])


POPEN_DEFAULT_KWARGS = {'stdin': sp.PIPE, 'stdout': sp.PIPE}


def _get_args_col(cols: int, fixed: int) -> int:
    term = shutil.get_terminal_size().columns
    # format "pretty": borders and whitespace padding
    # like: | spam | eggs |
    available = term - fixed - (cols + 1) - cols*2
    return max(0, available)


class ProcessMonitor(object):
    """Manager class to keep track of created subprocesses.

    Registered processes are cleaned up upon iterpreter exit().
    """
    _procs: ProcMap

    def __init__(self) -> None:
        atexit.register(self.purge)
        self._procs = {}

    def _list(self, procs: ProcMap) -> None:
        # self._tidy()

        # pass 1: get only the proc names to squeeze more spaces.
        names = []
        for pid, proc in procs.items():
            if isinstance(proc.args, str):
                name = proc.args
            else:
                name = os.path.basename(proc.args[0])
            names.append(
                cmd.limit_string(name, width=16, tail=False, pad=False)
            )
        name_col = max((len(name) for name in names), default=4)
        args_col = _get_args_col(4, name_col + 5 + 6)

        headers = ['name', 'pid', 'status']
        colwidths = [name_col, 5, 1]
        if args_col >= 16:
            headers.append('command')
            colwidths.append(args_col)

        # pass 2
        data = []
        for idx, (pid, proc) in enumerate(procs.items()):
            status = '-' if proc.poll() is None else str(proc.returncode)
            # command: don't include if terminal is extremely narrow.
            row = [names[idx], str(pid), status]
            if args_col >= 16:
                if isinstance(proc.args, str):
                    command = args
                else:
                    command = ' '.join(proc.args)
                row.append(command)
            data.append(row)

        print(
            tabulate(
                data,
                headers=headers,
                numalign=None,
                disable_numparse=True,
                tablefmt='pretty',
                maxcolwidths=colwidths if data else None,
            )
        )

    def list(self) -> None:
        """List all registered processes."""
        self._list(self._procs)
    ls = list

    def pgrep(self, pattern: str, flags: int = 0) -> None:
        """List processes matching *pattern*."""
        procs = {}
        for pid, proc in self._procs.items():
            if isinstance(proc.args, str):
                args = proc.args
            else:
                args = ' '.join(proc.args)
            if re.search(pattern, args, flags=flags):
                procs[pid] = proc
        self._list(procs)


    def tidy(self) -> None:
        """Discard all terminated processes."""
        # We're removing dead processes, so we need to operate on copy.
        for pid, proc in list(self._procs.items()):
            if proc.poll() is not None:
                del self._procs[pid]

    def add(
        self, args: T.Sequence[str], **kwargs: T.Mapping[str, T.Any]
    ) -> sp.Popen:
        """Wraps ``Popen`` to supply common default values for convenience.

        Other ``Popen`` kwargs might be of interest include:
        :shell:
            Execute in shell.
        :cwd:
        :env:
            Provide environments.
        :encoding:
        :errors:
        :text:
            Set stdio to open in text mode with specified encoding.
        """
        _kwargs = POPEN_DEFAULT_KWARGS.copy()
        _kwargs.update(kwargs)
        proc = sp.Popen(args, **_kwargs)
        self._procs[proc.pid] = proc
        return proc

    def proc(self, pid: int) -> sp.Popen:
        """Return ``subprocess.Popen`` object matching *pid*."""
        return self._procs[pid]

    def purge(self) -> None:
        """Terminate all registered processes."""
        for proc in self._procs.values():
            proc.terminate()


procmon = ProcessMonitor()
popen = procmon.add
