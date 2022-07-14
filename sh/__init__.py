#! /usr/bin/env python3

"""This package provides shell-like functionalities.
It is not intended to be used as a programming library for any serious project.

The focus of this package is on accomplishing shell jobs,
with less quirks of shells, with strong flow control provided by Python,
and (hopefully) with not too much typing chores as well.

The interfaces are awkward as a programming language;
rather, they're designed to be convenient on Python interpreter, not IDE.
"""

import os
import sys

from pathlib import Path
from shutil import rmtree as rm, move as mv

from pipe import (
    Pipe,
    chain,
    chain_with,
    dedup,
    groupby,
    islice,
    izip,
    select as apply,
    reverse,
    skip,
    skip_while,
    sort,
    t,
    tail,
    take,
    take_while,
    tee,
    transpose,
    uniq,
    where,
)

from ..pipes import (
    chunk,
    devnull,
    grep,
    iprint,
    like,
    match,
    notlike,
    notmatch,
    omit,
    pick,
    sub,
)
from . import core
from . import hash
from . import sevenzip
from . import subp
from .core import (
    cat, icat, cd, pwd, pushd, popd, ils, ls, cp, LineList as llist
)
from .hash import (
    digest,
    idigest,
    sha1sum,
    isha1sum,
    sha256sum,
    isha256sum,
    sha512sum,
    isha512sum,
    md5sum,
    imd5sum,
    crc32sum,
    icrc32sum,
)
from .subp import popen, procmon
from .sevenzip import Sevenzip


__all__ = [
    # Auto imports for convenience.
    'os',
    'sys',
    
    # pathlib
    'Path',

    # shutil
    'rm',
    'mv',

    # pipe
    'Pipe',
    'chain',
    'chain_with',
    'dedup',
    'groupby',
    'islice',
    'izip',
    'apply',
    'reverse',
    'skip',
    'skip_while',
    'sort',
    't',
    'tail',
    'take',
    'take_while',
    'tee',
    'transpose',
    'uniq',
    'where',

    # semper.pipes
    'like',
    'notlike',
    'match',
    'grep',
    'notmatch',
    'sub',
    'pick',
    'omit',
    'chunk',
    'iprint',
    'devnull',

    # core
    'cat', 'icat',
    'cd',
    'cp',
    'ls', 'ils',
    'llist',
    'popd',
    'pushd',
    'pwd',

    # hash
    'digest',
    'idigest',
    'sha1sum',
    'isha1sum',
    'sha256sum',
    'isha256sum',
    'sha512sum',
    'isha512sum',
    'md5sum',
    'imd5sum',
    'crc32sum',
    'icrc32sum',

    # subp
    'popen',
    'procmon',

    # sevenzip
    'sevenzip',
    'Sevenzip',
]
