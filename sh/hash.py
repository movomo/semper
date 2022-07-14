#! /usr/bin/env python3

"""This module provides posix shell-like file hashing interface."""

from __future__ import annotations

# import argparse
import binascii
import codecs
import hashlib
import re
import typing as T

from functools import partial
from pathlib import Path

from pipe import Pipe, chain_with

from . import core


# typedef
pathstr = T.NewType('pathstr', T.Union[str, Path])
TV = T.TypeVar('TV')


class HashSum(T.NamedTuple):
    name: Path
    hash: str
    binary: bool
    algorithm: str

    def __str__(self) -> str:
        return f'{self.hash} {"*" if self.binary else " "}{self.name}'

    def __eq__(self, other: T.Union[HashSum, str]) -> bool:
        if isinstance(other, type(self)):
            return self.hash == other.hash
        return self.hash == other


class HashCheck(T.NamedTuple):
    name: Path
    ok: bool
    detail: str


class _crc32(object):
    """Wrapper around ``binascii.crc32`` to make it look like from hashlib."""
    digest_size: int = 8
    name: str = 'crc32'

    _hash: int = 0

    def __init__(self, data: T.Optional[bytes] = None) -> None:
        if data is not None:
            self.update(data)

    def update(self, data: bytes):
        self._hash = binascii.crc32(data, self._hash)

    def digest(self) -> bytes:
        return codecs.decode(self.hexdigest(), encoding='hex')

    def hexdigest(self) -> str:
        return hex(self._hash)[2:]


def _define_parser():
    parser = core.NoExitArgumentParser(
        prog='{sha1, sha256, sha512, md5, crc32, ...}',
        description='''POSIX shell-like file hashing.
            Hashing is always done in binary mode.''',
        # error_on_exit=False,
    )

    # files
    parser.add_argument(
        'files',
        nargs='*',
        type=Path,
        help='''Files to process.
            With no file, *files* function arg must be provided.''',
    )

    group = parser.add_mutually_exclusive_group()
    # check
    group.add_argument(
        '-c',
        '--check',
        action='store_true',
        help='''Read hashes from files and check them.''',
    )
    # output
    group.add_argument(
        '-o',
        '--output',
        action='store_true',
        help='''Make checksum file for each input file.
            The format is "{filename}.{algorithm}.txt".''',
    )

    return parser


_P_CHECKSUM = re.compile(r'^([0-9a-f])+ [* ](.+)$', re.IGNORECASE)
_PARSER = _define_parser()

def _digest(
    files: T.Iterable[pathstr],
    alg: str,
    opts: T.Optional[str] = None
) -> T.Union[T.Iterable[HashSum], T.Iterable[HashCheck]]:
    opts = [] if opts is None else opts.split(' ')
    try:
        args = _PARSER.parse_args(opts)
    except core.ParserExit:
        return

    if alg in hashlib.algorithms_available:
        hasher = getattr(hashlib, alg)
    elif alg == 'crc32':
        hasher = _crc32

    for path in (core.expandpath(f) for f in args.files | chain_with(files)):
        if not path.is_file():
            continue
        if args.check:
            with path.open('r', encoding='utf-8') as check_in:
                for line in check_in:
                    if not (match := _P_CHECKSUM.search(line.rstrip())):
                        yield HashCheck('', False, 'invalid format')
                        continue
                    hash_ref, name = match.group(1, 2)
                    target = Path(name)
                    if not target.exists():
                        yield HashCheck(name, False, 'missing file')
                        continue
                    with target.open('rb') as target_in:
                        hash_got = hasher(target_in.read()).hexdigest()
                        if hash_ref == hash_ref:
                            yield HashCheck(name, True, '')
                        else:
                            yield HashCheck(name, False, 'mismatching hash')

        else:
            with path.open('rb') as target_in:
                hash_got = hasher(target_in.read()).hexdigest()
                hash = HashSum(path, hash_got, True, alg)
                if args.output:
                    outpath = Path(str(path) + f'.{alg}.txt')
                    with outpath.open('w', encoding='utf-8') as check_out:
                        check_out.write(str(hash))
                yield hash

def digest(
    alg: str,
    opts: T.Optional[str] = None
) -> T.Union[T.Iterable[HashSum], T.Iterable[HashCheck]]:
    return _digest([], alg, opts=opts)

idigest = Pipe(_digest)

sha1sum = partial(digest, 'sha1')
isha1sum = idigest('sha1')

sha256sum = partial(digest, 'sha256')
isha256sum = idigest('sha256')

sha512sum = partial(digest, 'sha512')
isha512sum = idigest('sha512')

md5sum = partial(digest, 'md5')
imd5sum = idigest('md5')

crc32sum = partial(digest, 'crc32')
icrc32sum = idigest('crc32')
