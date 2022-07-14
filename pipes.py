#! /usr/bin/env python3

"""This module implements some common operations through pipe."""

import fnmatch
import io
import os
import re
import sys
import typing as T

from operator import itemgetter
from pathlib import Path

from pipe import Pipe

# from .sh import core


def _expandpath(path: T.Union[str, Path]) -> Path:
    return os.path.expandvars(Path(path).expanduser())


@Pipe
def like(
    iterable: T.Iterable[T.Union[str, Path, T.Container]],
    pattern: str,
    key: T.Optional[T.Any] = None,
    invert: bool = False,
) -> T.Iterable[T.Union[str, T.Container]]:
    """Filter strings [not] matching the unix glob pattern given.

    .. code:: python
        >>> list(['ham', 'jam', 'spam', 'eggs'] | like('*s'))
        >>> ['eggs']

    The pre-initialized inverted version ``notlike`` is also provided.

    :iterable:
        Must be an iterable of str, Path, or,
        if *key* is provided, any subscriptable objects.
    :pattern:
        Matching is done with ``fnmatch.fnmatch`` wthout case sensitivity.
    :key:
        If iterable is not of simple str or Path,
        *key* must be provided to get the str item to match.
        Default is ``None``,
        so entries with actual ``None`` key cannot be accessed.
    :invert:
        If ``True``, items that does *not* match *pattern* will pass through
        instead.
        Default is ``False``.
    """
    for item in iterable:
        string = item if key is None else item[key]
        if isinstance(string, Path):
            string = str(string)
        if fnmatch.fnmatch(string, pattern):
            if not invert:
                yield item
        elif invert:
            yield item

notlike = like(invert=True)


@Pipe
def match(
    iterable: T.Iterable[T.Union[str, Path, T.Container]],
    pattern: T.Union[str, T.Pattern],
    flags: int = 0,
    key: T.Optional[T.Any] = None,
    only_matching: bool = False,
    invert: bool = False,
) -> T.Iterable[T.Union[str, T.Container]]:
    """Filter strings [not] matching the regular expression pattern given.

    .. code:: python
        >>> list(['ham', 'jam', 'spam', 'eggs'] | match('.a'))
        >>> ['ham', 'jam']

    The pre-initialized inverted version ``notmatch`` is also provided.
    ``grep`` is an alias of ``match``.

    :iterable:
        Must be an iterable of str, Path, or, if *key* is provided,
        any subscriptable and member-testable objects.
    :pattern:
        Matching is done with ``re.search``.
    :flags:
        Regular expression flags such as ``re.IGNORECASE``.
    :key:
        If iterable is not of simple str or Path,
        *key* must be provided to get the str item to match.
        Default is ``None``,
        so entries with actual ``None`` key cannot be accessed.
    :only_matching:
        Like ``--only-matching`` option of ``grep``,
        return only the matching part of the string instead of whole thing.
        This will force return strings even if input was not simple strings.
        Default is ``False``.
    :invert:
        If ``True``, items that does *not* match *pattern* will pass through
        instead.
        Default is ``False``.
    """
    p = re.compile(pattern, flags=flags)
    for item in iterable:
        string = item if key is None else item[key]
        if isinstance(string, Path):
            string = str(string)
        match = p.search(string)
        if match and not invert:
            if only_matching:
                yield match.group(0)
            else:
                yield item
        elif not match and invert:
            yield item

grep = match
notmatch = match(invert=True)

@Pipe
def sub(
    iterable: T.Iterable[T.Union[str, Path, T.Container]],
    pattern: T.Union[str, T.Pattern],
    replacement: str,
    flags: int = 0,
    count: int = 0,
    key: T.Optional[T.Any] = None,
    only_matching: bool = False,
) -> T.Iterable[T.Union[str, T.Container]]:
    """Replace strings [not] matching the regular expression pattern given.

    .. code:: python
        >>> list([{'menu': 'spam with eggs'}] | sub('eggs', 'spam', key='menu'))
        >>> [{'menu': 'spam with spam'}]

    - If items in *iterable* are simple strings, yield replaced string.
    - If not, modify the entry associated with *key* and yield the item.
      Caution is needed as modifications in this case happen in-place.

    :iterable:
        Must be an iterable of str, Path, or, if *key* is provided,
        any subscriptable and member-testable objects.
    :pattern:
        Matching is done with ``re.subn``.
    :replacement:
        May contain numeric(\\1, \\2) or named(\\g<name>) backrefereces.
    :flags:
        Regular expression flags such as ``re.IGNORECASE``.
    :count:
        Maximum number of replacements. Default is 0.
    :key:
        If iterable is not of simple str or Path,
        *key* must be provided to get the str item to match.
        Default is ``None``,
        so entries with actual ``None`` key cannot be accessed.
    :only_matching:
        Yield only the actually replaced items. Default is ``False``.
    """
    p = re.compile(pattern, flags=flags)
    for item in iterable:
        string = item if key is None else item[key]
        if ispath := isinstance(string, Path):
            string = str(string)
        repl, num = p.subn(replacement, string, count=count)

        if num:
            if key is None:
                yield repl if not ispath else Path(repl)
            else:
                item[key] = repl if not ispath else Path(repl)
                yield item
        else:
            if not only_matching:
                yield item

@Pipe
def pick(
    iterable: T.Iterable[T.Mapping], *keys: T.Iterable[T.Hashable]
) -> T.Iterable[T.Mapping]:
    """Pick entries with matching keys and return as new mapping of same type.

    .. code:: python
        >>> list([{'name': 'Lancelot', 'color': 'blue'},
                  {'name': 'Galahad', 'color': 'yellow'}]
                 | pick('color'))
        >>> [{'color': 'blue'}, {'color': 'yellow'}]

    :iterable:
        It must be an iterable of mapping.
        The mapping type needs to be able to be constructed from tuples.
    :keys:
        *keys* may be of anything that is hashable.
        It is not strictly required to be hashable, it's for API consistency.
    """
    keylen = len(keys)
    getter = itemgetter(*keys)
    for item in iterable:
        mapping = type(item)
        if keylen == 1:
            yield mapping(zip(keys, (getter(item),)))
        else:
            yield mapping(zip(keys, getter(item)))


@Pipe
def omit(
    iterable: T.Iterable[T.Mapping], *keys: T.Iterable[T.Hashable]
) -> T.Iterable[T.Mapping]:
    """Omit entries of matching keys and return as new mapping of same type.

    .. code:: python
        >>> list([{'name': 'Lancelot', 'color': 'blue'},
                  {'name': 'Galahad', 'color': 'yellow'}]
                 | omit('color'))
        >>> [{'name': 'Lancelot'}, {'name': 'Galahad'}]

    :iterable:
        It must be an iterable of mapping.
        The mapping type needs to be able to be constructed from tuples.
    :keys:
        *keys* needs to be an iterable of *hashable*.
        This requirement is enforced because the implementation converts it to
        a set.
    """
    banned = set(keys)
    for item in iterable:
        mapping = type(item)
        yield mapping((k, v) for k, v in item.items() if k not in banned)


@Pipe
def chunk(iterable: T.Iterable, size: int) -> T.Iterable[list]:
    """Split *iterable* into multiple lists of maximum length *size*.

    .. code:: python
        >>> list(range(1, 11) | chunk(3))
        >>> [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]

    :size:
        Output iterable will consist of lists that has *size* items maximum.
    """
    chunk = []
    for idx, item in enumerate(iterable):
        chunk.append(item)
        if idx % size == size - 1:
            yield chunk
            chunk = []
    else:
        if chunk:
            yield chunk


@Pipe
def iprint(
    iterable: T.Iterable,
    file: T.Union[str, Path, io.TextIOBase] = sys.stdout,
    mode: str = 'w',
    eop: bool = False,
) -> T.Iterable[None]:
    """Write to *file* line by line.

    :file:
        If *file* is a stream object, it will not be closed.
        If it is a str or Path, it will be opened and closed upon finish.
        Default is ``sys.stdout``.
    :mode:
        Write mode to open the file. Should either be 'w' or 'a'.
        Default is 'w'.
    :eop:
        "end of pipe". If ``False`` and *file* is not ``sys.stdout``,
        also yield the passed values as well as writing.
        Default is ``False``.
    """
    if close := not isinstance(file, io.TextIOBase):
        file = _expandpath(file).open(mode, encoding='utf-8')
    for item in iterable:
        file.write(str(item))
        file.write('\n')
        # if not eop and file is not sys.stdout:
            # yield item
    else:
        if close:
            file.close()


@Pipe
def devnull(iterable: T.Iterable) -> T.Iterable[None]:
    """Produce None, ignoring all input.
    This can absorb outputs, but not printed values.
    """
    pass
