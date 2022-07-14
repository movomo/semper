#! /usr/bin/env python3

import argparse
import glob
import os
import shutil
import sys
import typing as T
if os.name == 'nt':
    import stat
elif os.name != 'posix':
    raise NotImplementedError('Unsupported platform.')

from collections import UserList
from pathlib import Path

from semper.pipes import chunk


# typedef
pathstr = T.NewType('pathstr', T.Union[str, Path])


_DIRSTACK = []


class CWDPrompt(object):
    """Make interpreter prompt display cwd."""
    def __str__(self) -> str:
        return os.getcwd() + ' >>> '
sys.ps1 = CWDPrompt()


class ParserExit(argparse.ArgumentError):
    """Argument parsing stopped and cannot continue."""


class NoExitArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that doesnt exit on error, for interpreter usage."""
    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        raise ParserExit()


def _make_parser(name: str, data: list) -> argparse.ArgumentParser:
    parser = NoExitArgumentParser(prog=name)
    for args, kwargs in data | chunk(2):
        parser.add_argument(*args, **kwargs)
    return parser


def _has_wildcard(pathname: str) -> bool:
    """Return True if pathname contains any glob wildcard."""
    return glob.escape(pathname) != pathname

def _split_wildcard(path: Path) -> T.Tuple[Path, str]:
    """Split a path to the parent and the possible wildcard.

    Return value is a tuple containing parent: Path and child: str, such
    that parent.glob(child) would be a valid call.
    If path is a file and does not contain any wildcard, simply returns
    (path.parent, path.name). This applies for broken symlinks as well.
    If path is a directory and does not contain any wildcard, returns
    (path, '*').
    """
    parts = path.parts
    for idx, part in enumerate(parts):
        if _has_wildcard(str(part)):
            break
    else:
        if path.is_dir():
            return (path, '*')
        # elif path.is_file():
        else:
            return (path.parent, path.name)

    if idx == 0:
        return (Path(os.curdir), str(path))
    else:
        return (Path(path.join(*parts[:idx])), path.join(*parts[idx:]))



class LineList(UserList):
    def __init__(self, seq: T.Iterable = []) -> None:
        super().__init__(seq)

    def __repr__(self) -> str:
        return '\n'.join(str(item) for item in self.data)


class PathList(LineList):
    def __init__(self, seq: T.Optional[T.Iterable[T.Union[Path, str]]]) -> None:
        super().__init__(Path(p) for p in seq)



# expandpath

def expandpath(path: pathstr) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


# cd

def cd(path: pathstr) -> T.Union[Path, str]:
    try:
        dst = expandpath(path).resolve()
        os.chdir(dst)
        return dst
    except Exception as why:
        return why.args


def pwd() -> Path:
    return Path(os.getcwd())


def pushd(path: pathstr) -> T.Union[Path, str, None]:
    """Push to directory and, if successful, return resulting cwd."""
    path = expandpath(path)
    if path.is_dir():
        cwd = Path(os.getcwd())
        try:
            os.chdir(path)
            dst = path.resolve()
        except Exception as why:
            return why.args[0]
        _DIRSTACK.append(cwd)
        return dst.resolve()


def popd() -> T.Union[Path, str]:
    """pop from directory stack, and, if successful, return resulting cwd."""
    try:
        dst = _DIRSTACK[-1]
        os.chdir(dst)
    except Exception as why:
        return why.args[0]
    del _DIRSTACK[-1]
    return dst



# ls

def _identify_path(
    path: Path,
    st: os.stat_result,
    show_hidden: bool,
    show_system: bool,
    no_ordinary: bool,
) -> bool:
    """Return whether the pathname must be written to output or not.

    - On Unix, paths with leading dot names are hidden.
      Paths owned by root are considered system.
    - On Windows, paths are tested with their hidden/system attributes.
    """
    if os.name == 'nt':
        attr = st.st_file_attributes
        is_hidden = bool(attr & stat.FILE_ATTRIBUTE_HIDDEN)
        is_system = bool(attr & stat.FILE_ATTRIBUTE_SYSTEM)
    elif os.name == 'posix':
        is_hidden = path.name.startswith('.')
        is_system = (st.st_uid == 0)

    if is_hidden or is_system:
        if is_hidden and not show_hidden:
            return False
        if is_system and not show_system:
            return False
    elif no_ordinary:
        return False

    return True

def _filter_path(
    path: Path,
    st: os.stat_result,
    absolute: bool,
    file: bool,
    dir: bool,
    hidden: bool,
    system: bool,
    no_ordinary: bool
) -> T.Optional[Path]:
    """Test and return path, given criteria. If test fails, return None."""
    if file and not path.is_file():
        return
    if dir and not path.is_dir():
        return
    if _identify_path(path, st, hidden, system, no_ordinary):
        if absolute:
            return path.resolve()
        else:
            return path

_lsparser = _make_parser(
    'ls',
    [
        ['patterns'],
        {'nargs': '*', 'default': [os.path.join(os.curdir, '*')]},
        ['-a', '--absolute'],
        {'action': 'store_true'},
        ['-r', '--recursive'],
        {'action': 'store_true'},
        ['-hi', '--hidden'],
        {'action': 'store_true'},
        ['-sys', '-rt', '--system', '--root'],
        {'action': 'store_true'},
        ['-no', '--no-ordinary'],
        {'action': 'store_true'},
    ]
)
_group = _lsparser.add_mutually_exclusive_group()
_group.add_argument('-f', '--file', '--file-only', action='store_true')
_group.add_argument('-d', '--dir', '--directory-only', action='store_true')

def ils(opts: T.Optional[str] = None) -> T.Iterable[Path]:
    """Iterator version of ls."""
    try:
        args = _lsparser.parse_args([] if opts is None else opts.split(' '))
    except ParserExit:
        return

    done = set()
    for wc in args.patterns:
        wc = expandpath(wc)
        parent, name = _split_wildcard(wc)
        if args.recursive:
            globber = parent.rglob
        else:
            globber = parent.glob

        for path in globber(name):
            abs_path = path.resolve()
            if abs_path in done:
                continue

            st = path.lstat()
            path = _filter_path(
                path,
                st,
                args.absolute,
                args.file,
                args.dir,
                args.hidden,
                args.system, args.
                no_ordinary
            )
            if path is not None:
                yield path if args.absolute else path.relative_to(parent)
                done.add(abs_path)

def ls(opts: T.Optional[str] = None) -> PathList:
    """This is a hasty version of ils."""
    return PathList(path for path in ils(opts))



# cat

def icat(path: pathstr) -> T.Iterable[str]:
    """Lazy version of ``icat``.

    This can be dangerous if attempted to modify the file at the end of pipe.
    """
    path = expandpath(path)
    with path.open('r', encoding='utf-8') as text_r:
        for line in text_r:
            yield line.rstrip('\n')

def cat(path: pathstr) -> T.Sequence[str]:
    """Read a text file and return it line by line."""
    return LineList(icat(path))



# cp

_cpparser = _make_parser(
    'cp',
    [
        ['src'],
        {},
        ['dst'],
        {},
        ['-s', '--symlink', '--preserve-symlinks'],
        {'action': 'store_true', 'help': "Preserve symlinks. (don't follow)"},
        ['-p', '--parents'],
        {'action': 'store_true', 'help': "Merge/overwrite collisions."},
    ]
)

def cp(opts: str) -> T.Optional[str]:
    """Wrapper around ``shutil.copy2`` and ``shutil.copytree``."""
    try:
        args = _cpparser.parse_args(opts.split(' '))
    except ParserExit:
        return
    src = str(expandpath(args.src))
    dst = str(expandpath(args.dst))
    try:
        if os.path.isfile(src):
            shutil.copy2(src, dst, follow_symlinks=(not args.symlink))
        elif os.path.isdir(src):
            shutil.copytree(
                src, dst, symlinks=args.symlink, dirs_exit_ok=args.parents
            )
    except Exception as why:
        return why.args[0]



# structcmp

class structcmp(object):
    """File extension-agnostic comparison of two directories.

    Imitation of ``filecmp.dircmp``, the purpose of structcmp is to compare
    directories that must have the same structure, but with different file ext.
    Example of such includes one directory of main files and another directory
    of auxiliary files, such as image files for ai training and the text files
    defining their labels.

    Unlike ``dircmp``, this does not perform individual file comparison,
    just their existence.
    """
    left: Path
    right: Path
    left_files: PathList
    right_files: PathList
    common: PathList
    left_only: PathList
    right_only: PathList

    _left: T.Set[Path]
    _right: T.Set[Path]
    _lazy_attrs: set = {
        'left_files', 'right_files', 'common', 'left_only', 'right_only'
    }
    _cmp_done: T.Mapping[str, bool] = {k: False for k in _lazy_attrs}
    _cmp_done['init'] = False

    def __init__(
        self,
        left: pathstr,
        right: pathstr,
    ) -> None:
        self.left = expandpath(left)
        self.right = expandpath(right)
        self._cmp_done = self._cmp_done.copy()

    def summary(self):
        """Print summary of comparison between *left* and *right*."""
        print(f'Total stems in left: {len(self.left_files)}')
        print(f'Total stems in right: {len(self.right_files)}')
        print(f'Total common stems: {len(self.common)}')
        print(f'Total common stems: {len(self.common)}')
        print(f'Total unique stems in left: {len(self.left_only)}')
        print(f'Total unique stems in right: {len(self.right_only)}')

    def _cmp(self):
        self._left = set(p.parent / p.stem for p in self.left.rglob('*'))
        self._right = set(p.parent / p.stem for p in self.right.rglob('*'))
        self._cmp_done['init'] = True

    def _build_left_files(self):
        self.left_files = sorted(PathList(self._left))
        self._cmp_done['left_files'] = True
    def _build_right_files(self):
        self.right_files = sorted(PathList(self._right))
        self._cmp_done['right_files'] = True
    def _build_common(self):
        self.common = sorted(PathList(self._left & self._right))
        self._cmp_done['common'] = True
    def _build_left_only(self):
        self.left_only = sorted(PathList(self._left - self._right))
        self._cmp_done['left_only'] = True
    def _build_right_only(self):
        self.right_only = sorted(PathList(self._right - self._left))
        self._cmp_done['right_only'] = True

    _methods = {
        'left_files': _build_left_files,
        'right_files': _build_right_files,
        'common': _build_common,
        'left_only': _build_left_only,
        'right_only': _build_right_only,
    }

    def __getattr__(self, name):
        if not self._cmp_done['init']:
            self._cmp()
        if not self._cmp_done[name] and name in self._lazy_attrs:
            self._methods['_build' + name](self)
        return getattr(self, name)
