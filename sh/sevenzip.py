#! /usr/bin/env python3

"""This module provides an interface wrapped around 7-Zip command line."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
import typing as T
import winreg

from collections import abc, UserDict
from pathlib import Path

from . import subp


# typedef
pathstr = T.NewType('pathstr', T.Union[str, Path])


def _locate() -> T.Optional[str]:
    if os.name == 'nt':
        # If we're on Windows, first try the registry.
        try:
            with winreg.OpenKeyEx(
                winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\7-Zip'
            ) as key:
                # Doesn't matter if the interpreter is on x86 or amd64,
                # just try both.
                for name in ('Path64', 'Path'):
                    try:
                        path = os.path.join(
                            winreg.QueryValueEx(key, name)[0], '7z.exe'
                        )
                        if os.path.exists(path):
                            return path
                    except FileNotFoundError:
                        # This catches NotFound from winreg,
                        # incase subkeys don't exist.
                        pass
        except FileNotFoundError:
            pass

        # Looking up in the PATH is mostly for posix,
        # but it might work on Windows too if things like chocolatey is involved.
        # The console-only version '7zr' might exist too.
        for name in ('7z', '7zr'):
            if (path := shutil.which(name)) is not None:
                return path

    else:
        # Recent version of 7-Zip comes with official Linux port.
        # Their executable names are: 7zz for dynamic and 7zzs for static.
        # However they don't seem to have been properly packaged yet,
        # so we just don't know what its actual executable name will be.
        # in any case, this will try to locate the official names first
        # and fall back to 7z, whether it's official or from p7zip.
        for name in ('7zz', '7zzs', '7z'):
            if (path := shutil.which(name)) is not None:
                return path

def _locate_auxiliary(exe: T.Union[str, None], aux: str) -> T.Union[str, None]:
    """Used to locate 7zG.exe and 7zFM.exe on Windows."""
    if os.name != 'nt' or exe is None:
        return
    parent = os.path.dirname(exe)
    other_exe = os.path.join(parent, aux)
    if os.path.exists(other_exe):
        return other_exe


class CompressionMethod(UserDict):
    """"""
    name: str
    _sortkey: int = 64
    _default: dict = {}

    def __init__(self, initialdata = ()) -> None:
        if isinstance(initialdata, abc.Mapping):
            _data = initialdata.items()
        else:
            _data = initialdata
        args = [(k, v) for k, v in _data if k in self._default]
        super().__init__(args)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.data!r})'

    def __str__(self) -> str:
        """Return a template format string (to be filled with index)."""
        return (
            '-m{}='
            + ':'.join([self.name, *(f'{k}={v}' for k, v in self.items())])
        )

    def __setitem__(self, key, value):
        if key not in self._default:
            raise KeyError(f"unallowed key: {key!r}")
        self.data[key] = value


class CompressionFilter(CompressionMethod):
    """Filters should go first in the method chain."""
    _sortkey: int = 0


class LZMAMethod(CompressionMethod):
    """LZ-based algorithm

    LZMA is an algorithm based on Lempel-Ziv algorithm.
    It provides very fast decompression
    (about 10-20 times faster than compression).
    Memory requirements for compression and decompression also are different
    (see d={Size}[b|k|m|g] switch for details).
    """
    name = 'LZMA'
    _default = {
        'a': 1,
        'd': 24,
        'mf': 'bt4',
        'fb': 32,
        'mc': 32,
        'lc': 3,
        'lp': 0,
        'pb': 2,
    }

    def fast_compression(self, value: int) -> LZMAMethod:
        """Sets compression mode: 0 = fast, 1 = normal. Default value is 1."""
        self['a'] = value
        return self
    a = fast_compression

    def dict_size(self, value: T.Union[int, str]) -> LZMAMethod:
        """Sets Dictionary size for LZMA.

        You must specify the size in bytes, kilobytes, or megabytes.
        The maximum value for dictionary size is 1536 MB, but 32-bit version of
        7-Zip allows to specify up to 128 MB dictionary.
        Default values for LZMA are 24 (16 MB) in normal mode,
        25 (32 MB) in maximum mode (-mx=7) and 26 (64 MB) in ultra mode (-mx=9).
        If you do not specify any symbol from the set [b|k|m|g],
        the dictionary size will be calculated as DictionarySize = 2^Size bytes.
        For decompressing a file compressed by LZMA method with dictionary
        size N, you need about N bytes of memory (RAM) available.
        """
        self['d'] = value
        return self
    dictsize = dict_size
    d = dict_size

    def match_finder(self, value: str) -> LZMAMethod:
        """Sets Match Finder for LZMA. Default method is bt4.

        Algorithms from hc* group don't provide a good compression ratio,
        but they often work pretty fast in combination with fast mode (a=0).
        Memory requirements depend on dictionary size
        (parameter "d" in table below).

        =====   =================   =============== ===========================
        MF_ID   Dictionary          Memory Usage    Description
        -----   -----------------   --------------- ---------------------------
        bt2                         9.5 * d + 4 MB  Binary Tree 2 bytes hashing
        bt3                         11.5 * d + 4 MB Binary Tree 3 bytes hashing
        bt4     64 KB ... 48 MB     11.5 * d + 4 MB Binary Tree 4 bytes hashing
        bt4     64 MB ... 1024 MB   10.5 * d + 4 MB Binary Tree 4 bytes hashing
        hc4     64 KB ... 48 MB     7.5 * d + 4 MB  Hash Chain  4 bytes hashing
        hc4     64 MB ... 1024 MB   6.5 * d + 4 MB  Hash Chain  4 bytes hashing
        =====   =================   =============== ===========================

        Note: Your operation system also needs some amount of physical memory
        for internal purposes. So keep at least 32MB of physical memory unused.
        """
        self['mf'] = value
        return self
    mf = match_finder

    def fast_bytes(self, value: int) -> LZMAMethod:
        """Sets number of fast bytes for LZMA.

        It can be in the range from 5 to 273.
        The default value is 32 for normal mode and 64 for maximum and ultra
        modes. Usually, a big number gives a little bit better compression
        ratio and slower compression process.
        """
        self['fb'] = value
        return self
    fb = fast_bytes

    def match_finder_cycles(self, value: int) -> LZMAMethod:
        """Sets number of cycles (passes) for match finder.

        It can be in range from 0 to 1000000000.
        Default value is (16 + number_of_fast_bytes / 2) for BT* match finders
        and (8 + number_of_fast_bytes / 4) for HC4 match finder.
        If you specify mc=0, LZMA will use default value.
        Usually, a big number gives a little bit better compression ratio
        and slower compression process.
        For example, mf=HC4 and mc=10000 can provide almost the same
        compression ratio as mf=BT4.
        """
        self['mc'] = value
        return self
    mc = match_finder_cycles

    def literal_context_bits(self, value: int) -> LZMAMethod:
        """Sets the number of literal context bits (high bits of previous literal).

        It can be in range from 0 to 8. Default value is 3.
        Sometimes lc=4 gives gain for big files.
        """
        self['lc'] = value
        return self
    lc = literal_context_bits

    def literal_pos_bits(self, value: int) -> LZMAMethod:
        """Sets the number of literal pos bits (low bits of current position for literals).

        It can be in the range from 0 to 4. The default value is 0.
        The lp switch is intended for periodical data when the period is
        equal to 2^value (where lp=value).
        For example, for 32-bit (4 bytes) periodical data you can use lp=2.
        Often it's better to set lc=0, if you change lp switch.
        """
        self['lp'] = value
        return self
    lp = literal_pos_bits

    def pos_bits(self, value: int) -> LZMAMethod:
        """Sets the number of pos bits (low bits of current position).
        It can be in the range from 0 to 4. The default value is 2.
        The pb switch is intended for periodical data when the period is
        equal 2^value (where lp=value).
        """
        self['pb'] = value
        return self
    pb = pos_bits

class LZMA2Method(LZMAMethod):
    """LZMA-based algorithm

    LZMA2 is modified version of LZMA.
    it provides the following advantages over LZMA:

    - Better compression ratio for data than can't be compressed.
      LZMA2 can store such blocks of data in uncompressed form.
      Also it decompresses such data faster.
    - Better multithreading support.
      If you compress big file, LZMA2 can split that file to chunks and
      compress these chunks in multiple threads.
    """
    name = 'LZMA2'
    _default = {
        'a': 1,
        'd': 24,
        'mf': 'bt4',
        'fb': 32,
        'mc': 32,
        'lc': 3,
        'lp': 0,
        'pb': 2,
        'c': 24 * 4,
    }

    def chunk_size(self, value: T.Union[int, str]) -> LZMA2Method:
        """Sets Chunk size

        If you don't specify ChunkSize, LZMA2 sets it to
        max(DictionarySize, min(256M, max(1M, DictionarySize * 4))).

        LZMA2 also supports all LZMA parameters,
        but lp+lc cannot be larger than 4.

        LZMA2 uses: 1 thread for each chunk in x1 and x3 modes;
        and 2 threads for each chunk in x5, x7 and x9 modes.
        If LZMA2 is set to use only such number of threads required for one
        chunk, it doesn't split stream to chunks.
        So you can get different compression ratio for different number of
        threads.
        You can get the best compression ratio, when you use 1 or 2 threads.
        """
        self['c'] = value
        return self
    chunksize = chunk_size
    c = chunk_size

class PPMdMethod(CompressionMethod):
    """Dmitry Shkarin's PPMdH with small changes

    PPMd is a PPM-based algorithm.
    This algorithm is mostly based on Dmitry Shkarin's PPMdH source code.
    PPMd provides very good compression ratio for plain text files.
    There is no difference between compression speed and decompression speed.
    Memory requirements for compression and decompression also are the same.
    """
    name = 'PPMd'
    _default = {'mem': 24, 'o': 6}

    def memory_size(self, value: int) -> PPMdMethod:
        self['mem'] = value
        return self
    memorysize = memory_size
    mem = memory_size

    def model_order(self, value: int) -> PPMdMethod:
        self['o'] = value
        return self
    o = model_order

class BZip2Method(CompressionMethod):
    """BWT algorithm"""
    name = 'BZip2'

class DeflateMethod(CompressionMethod):
    """LZ+Huffman"""
    name = 'Deflate'

class CopyMethod(CompressionMethod):
    """No compression"""
    name = 'Copy'

class DeltaFilter(CompressionFilter):
    """Delta filter"""
    name = 'Delta:1'

    def delta_offset(self, value: int) -> DeltaFilter:
        """Set delta offset in bytes.

        For example, to compress 16-bit stereo WAV files,
        you can set "0=Delta:4".
        Default delta offset is 1.
        """
        self.name = f'Delta:{value}'
        return self

class BCJFilter(CompressionFilter):
    """converter for x86 executables"""
    name = 'BCJ'

class BCJ2Filter(BCJFilter):
    """converter for x86 executables (version 2)

    BCJ2 is a Branch converter for 32-bit x86 executables (version 2).
    It converts some branch instructions for increasing further compression.

    A BCJ2 encoder has one input stream and four output streams:

    - s0: main stream. It requires further compression.
    - s1: stream for converted CALL values. It requires further compression.
    - s2: stream for converted JUMP values. It requires further compression.
    - s3: service stream. It is already compressed.

    If LZMA is used, the size of the dictionary for streams s1 and s2 can be
    much smaller (512 KB is enough for most cases) than the dictionary size for
    stream s0.
    """
    name = 'BCJ2'
    _default = {'d': '64m'}

    def dict_size(self, value: T.Union[int, str]) -> BCJ2Filter:
        self['d'] = value
        return self
    dictsize = dict_size
    d = dict_size

class ARMFilter(CompressionFilter):
    """converter for ARM (little endian) executables"""
    name = 'ARM'

class ARMTFilter(CompressionFilter):
    """converter for ARM Thumb (little endian) executables"""
    name = 'ARMT'

class IA64Filter(CompressionFilter):
    """converter for IA-64 executables"""
    name = 'IA64'

class PPCFilter(CompressionFilter):
    """converter for PowerPC (big endian) executables"""
    name = 'PPC'

class SPRACFilter(CompressionFilter):
    """converter for SPARC executables"""
    name = 'SPARC'


class SevenzipOptions(UserDict):
    """"""
    method_chain: T.Sequence[T.Union[CompressionFilter, CompressionMethod]]
    _ref: dict = {
        'ao': {'accept': {'a', 'o', 'u', 't'}},
        'i': {'container': set},
        'x': {'container': set},
        'slp': {'accept': {'', '-'}},
        'ssc': {'accept': {'', '-'}},
        'y': {'accept': {''}},
        'mx': {'accept': {0, 1, 3, 5, 7, 9}},
        'myx': {'accept': {0, 1, 3, 5, 7, 9}},
        'mqs': {'accept': {'on', 'off'}},
        'mhc': {'accept': {'on', 'off'}},
        'mhe': {'accept': {'on', 'off'}},
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.method_chain = []

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.data!r})'

    def __str__(self) -> str:
        return ' '.join(self.args())

    def __or__(self, other: T.Mapping) -> SevenzipOptions:
        """Return an updated copy of itself with *other*."""
        opts = self.copy()
        opts.update(other)
        return opts

    def __ior__(self, other: T.Mapping) -> SevenzipOptions:
        """Update with *other*."""
        self.update(other)
        return self

    def __setitem__(self, key: str, value) -> None:
        """Do some validation before setting if possible."""
        if key in self._ref:
            if (
                'accept' in self._ref[key]
                and value not in self._ref[key]['accept']
            ):
                raise ValueError(f"value must be in {self._acceptable[key]!r}")
        self.data[key] = value

    def update(
        self,
        other: T.Optional[T.Union[T.Mapping, T.Iterable[tuple]]] = None,
        **kwargs: T.Mapping[str, ...],
    ) -> None:
        """Update with *other*.

        For atomic values, original values are overridden.
        For sequences and mappings, they are extended/updated.
        For sets, they are joined together.
        """
        if isinstance(other, abc.Mapping):
            other = other.items()
        for k, v in other:
            # Preemptive entry generation for type constraint
            if k not in self and k in self._ref and'container' in self._ref[k]:
                self[k] = self._ref[k]['container']()
            if k not in self:
                self[k] = v
                continue

            if isinstance(self[k], abc.Set):
                if not isinstance(v, abc.Set):
                    raise ValueError(f"value type for key {k!r} mismatch")
                self[k] |= v
            elif isinstance(self[k], abc.MutableSequence):
                if not isinstance(v, abc.Iterable):
                    raise ValueError(f"value type for key {k!r} mismatch")
                self[k].extend(v)
            elif isinstance(self[k], abc.MutableMapping):
                if (
                    not isinstance(v, abc.Mapping)
                    and not isinstance(v, abc.Iterable)
                ):
                    raise ValueError(f"value type for key {k!r} mismatch")
                self[k].update(v)
            else:
                self[k] = v

    def extend(self, others: T.Iterable[T.Mapping]) -> SevenzipOptions:
        """Batch version of ``update``.

        This doesn't make it copy itself,
        but returns self anyway for convenience.
        """
        if isinstance(others, abc.Mapping):
            raise
        for other in others:
            self.update(other)
        return self

    def args(self, pick: T.Optional[T.Set[str]] = None) -> T.Iterable[str]:
        """Convert options to iterable of commandline args.

        :pick:
            If given (as a member-testable object), only the values whose keys
            can be found in it are included in the resulting arg list.
        """
        for key, value in self.items():
            if pick is not None and key not in pick:
                continue
            if key.startswith('m'):
                key += '='
            if not isinstance(value, str) and hasattr(value, '__iter__'):
                for v in value:
                    yield f'-{key}{v}'
            else:
                yield f'-{key}{value}'
        # add method chain
        if pick is None or 'm' in pick:
            for idx, method in enumerate(self.method_chain):
                yield str(method).format(idx)

    def overwrite_mode(self, value: str) -> SevenzipOptions:
        """Specifies the overwrite mode during extraction,
        to overwrite files already present on disk.

        .. code::
            -ao[a | s | t | u ]

        *value* must be one of **a**, **s**, **u**, **t**.

        ======  ===============================================================
        Switch  Description
        ------  ---------------------------------------------------------------
        -aoa    Overwrite All existing files without prompt.
        -aos    Skip extracting of existing files.
        -aou    aUto rename extracting file
                (for example, name.txt will be renamed to name_1.txt).
        -aot    auto rename existing file
                (for example, name.txt will be renamed to name_1.txt).
        ======  ===============================================================
        """
        self['ao'] = value
        return self
    ao = overwrite_mode

    def include(
        self,
        *patterns: T.Sequence[str],
        recurse_type: str = 'r',
        file_ref_type: str = '!',
    ) -> SevenzipOptions:
        """Specifies additional include filenames and wildcards.

        Multiple include switches are supported.
        *patterns* will be enclosed in double quotes.

        .. code::
            -i[<recurse_type>]<file_ref>

            <recurse_type> ::= r[- | 0]
            <file_ref> ::= @{listfile} | !{wildcard}

        :recurse_type:
            Specifies how wildcards and file names in this switch must be used.
            If this option is not given, then the global value,
            assigned by the -r (Recurse) switch will be used.

            **This method's default is 'r'.**

            .. code::
                -r[- | 0]

            ======  ======================================================
            Switch  Description
            ------  ------------------------------------------------------
            -r      Enable recurse subdirectories.
            -r-     Disable recurse subdirectories.
                    This option is default for all commands.
            -r0     Enable recurse subdirectories only for wildcard names.
            ======  ======================================================

        :file_ref_type:
            Specifies filenames and wildcards, or a list file,
            for files to be processed.

            **This method's default is '!'.**

            .. code::
                <file_ref> ::= @{listfile} | !{wildcard}
        """
        for pattern in patterns:
            self['i'].add(f'{recurse_type}{file_ref_type}"pattern"')
        return self
    i = include

    def exclude(
        self,
        *patterns: T.Sequence[str],
        recurse_type: str = 'r',
        file_ref_type: str = '!',
    ) -> SevenzipOptions:
        """Specifies which filenames or wildcarded names must be excluded
        from the operation.

        Multiple exclude switches are supported.
        *patterns* will be enclosed in double quotes.

        .. code::
            -x[<recurse_type>]<file_ref>

            <recurse_type> ::= r[- | 0]
            <file_ref> ::= @{listfile} | !{wildcard}

        :recurse_type:
            Specifies how wildcards and file names in this switch must be used.
            If this option is not given, then the global value,
            assigned by the -r (Recurse) switch will be used.

            **This method's default is 'r'.**

            .. code::
                -r[- | 0]

            ======  ======================================================
            Switch  Description
            ------  ------------------------------------------------------
            -r      Enable recurse subdirectories.
            -r-     Disable recurse subdirectories.
                    This option is default for all commands.
            -r0     Enable recurse subdirectories only for wildcard names.
            ======  ======================================================

        :file_ref_type:
            Specifies filenames and wildcards, or a list file,
            for files to be processed.

            **This method's default is '!'.**

            .. code::
                <file_ref> ::= @{listfile} | !{wildcard}
        """
        for pattern in patterns:
            self['x'].add(f'{recurse_type}{file_ref_type}"pattern"')
        return self
    x = exclude

    def output(self, path: pathstr) -> SevenzipOptions:
        """Specifies a destination directory where files are to be extracted.

        This switch can be used only with extraction commands.
        *path* will be enclosed in double quotes.

        .. code::
            -o{dir_path}

        :{dir_path}:
        This is the destination directory path.
        It's not required to end with a backslash.
        If you specify * in {dir_path},
        7-Zip substitutes that * character to archive name.
        """
        self['o'] = path
        return self
    o = output

    def password(
        self, ask: bool = True, value: T.Optional[str] = None
    ) -> SevenzipOptions:
        """Specifies password.

        .. code::
            -p{password}

        {password}
            Specifies password.

        :ask:
            If ``True`` (default), password is asked through echoless query.
        :value:
            If *ask* is ``True``, *value* is ignored.
        """
        if ask:
            value = getpass.getpass()
        self['p'] = value
        return self
    p = password

    def set_large_pages(self, value: bool) -> SevenzipOptions:
        """Sets Large Pages mode.

        .. code::
            -slp[-]

        ======  ========================================
        Switch  Description
        ------  ----------------------------------------
        -slp    Enables Large Pages mode.
        -slp-   Disables Large Pages mode.
                This option is default for all commands.
        ======  ========================================

        Large Pages mode increases the speed of compression.
        However, there is a pause at the start of compression while 7-Zip
        allocates the large pages in memory.
        If 7-Zip can't allocate large pages, it allocates usual small pages.
        Also, the Windows Task Manager doesn't show the real memory usage of
        the program, if 7-Zip uses large pages.
        This feature doesn't work on Windows 2000 / 32-bit Windows XP.
        Also, it can require administrator's rights for your system.
        The recommended size of RAM for this feature is 3 GB or more.
        To install this feature, you must run the 7-Zip File Manager with
        administrator's rights at least once, close it, and then reboot the
        system.

        Notes: if you use -slp mode in old Windows version, your Windows system
        can hang for several seconds when 7-zip allocates memory blocks.
        Windows can hang other tasks for that time.
        It can look like full system hang, but then it resumes.
        It was so in old Windows versions.
        But modern Windows versions (Windows 7 / Windows 10) can allocate
        "Large pages" faster than previous Windows versions.

        Also it's senseless to use -slp mode to compress small data sets
        (less than 100 MB).
        But if you compress big data sets (100 MB or more) with LZMA/LZMA2
        method with large dictionary, you can get 5%-10% speed improvement
        with -slp mode.
        """
        self['slp'] = '' if value else '-'
        return self
    large_pages = set_large_pages
    slp = set_large_pages

    def set_sensitive_case(self, value: bool) -> SevenzipOptions:
        """Sets sensitive case mode for file names.

        .. code::
            -scs[-]

        ======  ==============================================================
        Switch  Description
        ------  --------------------------------------------------------------
        -ssc    Set case-sensitive mode. It's default for Posix/Linux systems.
        -ssc-   Set case-insensitive mode. It's default for Windows systems.
        ======  ==============================================================
        """
        self['ssc'] = '' if value else '-'
        return self
    sensitive_case = set_sensitive_case
    case_sensitive = set_sensitive_case
    ssc = set_sensitive_case

    def yes(self, value: T.Optional[bool] = True) -> SevenzipOptions:
        """Disables most of the normal user queries during 7-Zip execution.

        You can use this switch to suppress overwrite queries in the e
        (Extract) and x (Extract with full paths) commands.
        """
        if value:
            self['y'] = ''
        else:
            del self['y']
        return self
    y = yes

    def type(self, value: str) -> SevenzipOptions:
        """Specifies the type of archive.

        .. code::
            -t{archive_type}[:s{Size}][:r][:e][:a]

        {archive_type}
            Specifies the type of archive.
            It can be: *, #, 7z, xz, split, zip, gzip, bzip2, tar, ....
        *:r
            Default mode. 7-Zip opens archive and subfile,
            if it's supported by format.
        *
            Opens only one top level archive.
        *:s{Size}[b | k | m | g]
            Sets upper limit for start of archive position.
            Default scan size is 8 MBytes "*:s8m".
            Example: "*:s0" means that it will open only file that has no any
            stub before archive.
        #
            Opens file in Parser mode, and ignores full archives.
        #:a
            Same as *, but it opens files with unknown extensions that contain
            archives in Parser Mode.
        #:e
            Opens file in Parser mode and checks all byte positions as start of
            archive.
            If ``-t{archive_type}`` switch is not specified, 7-Zip uses
            extension of archive filename to detect the type of archive.
            If you create new archive, ``-t{archive_type}`` switch is not
            specified and there is no extension of archive,
            7-Zip will create .7z archive.

        If ``-t{archive_type}`` switch is not specified and archive name
        contains incorrect extension, the program will show the warning.

        It's possible to use the combined type (for example, mbr.vhd) for
        "Extract" and "List" commands for some archives.

        When you extract archive of some types that contains another archive
        without compression (for example, MBR in VHD), 7-Zip can open both
        levels in one step.
        If you want to open/extract just top level archive, use ``-t*`` switch.

        Note: xz, gzip and bzip2 formats support only one file per archive.
        If you want to compress more than one file to these formats, create a
        tar archive at first, and then compress it with your selected format.
        """
        self['t'] = value
        return self
    t = type

    def methods(
        self, *values: T.Union[CompressionFilter, CompressionMethod]
    ) -> SevenzipOptions:
        """Sets compression method. You can use any number of methods.
        The default method is LZMA2.

        {N} sets the index number of method in methods chain.
        Numbers must begin from 0.
        Methods that have smaller numbers will be used before others.

        Parameters must be in one of the following forms:

        - {ParamName}={ParamValue}.
        - {ParamName}{ParamValue}, if {ParamValue} is number and
          {ParamName} doesn't contain numbers.

        Supported methods:

        ========    =========================================
        MethodID    Description
        --------    -----------------------------------------
        LZMA        LZ-based algorithm
        LZMA2       LZMA-based algorithm
        PPMd        Dmitry Shkarin's PPMdH with small changes
        BZip2       BWT algorithm
        Deflate     LZ+Huffman
        Copy        No compression
        ========    =========================================

        Supported filters:

        ========    =========================================
        MethodID    Description
        --------    -----------------------------------------
        Delta       Delta filter
        BCJ         converter for x86 executables
        BCJ2        converter for x86 executables (version 2)
        ARM         converter for ARM (little endian) executables
        ARMT        converter for ARM Thumb (little endian) executables
        IA64        converter for IA-64 executables
        PPC         converter for PowerPC (big endian) executables
        SPARC       converter for SPARC executables
        ========    =========================================

        Filters increase the compression ratio for some types of files.
        Filters must be used with one of the compression method
        (for example, BCJ + LZMA).
        """
        self.method_chain.extend(values)
        return self
    m = methods

    def level(self, value: int) -> SevenzipOptions:
        """Sets level of compression

        .. code::
            x=[0 | 1 | 3 | 5 | 7 | 9 ]

        ===== ====== ========== ========= =========== ====== ===============
        Level Method Dictionary FastBytes MatchFinder Filter Description
        ----- ------ ---------- --------- ----------- ------ ---------------
        0     Copy                                           No compression.
        1     LZMA2  64 KB      32        HC4          BCJ   Fastest
        3     LZMA2  1 MB       32        HC4          BCJ   Fast
        5     LZMA2  16 MB      32        BT4          BCJ   Normal
        7     LZMA2  32 MB      64        BT4          BCJ   Maximum
        9     LZMA2  64 MB      64        BT4          BCJ2  Ultra
        ===== ====== ========== ========= =========== ====== ===============

        Note: "x" works as "x=9".
        """
        self['mx'] = value
        return self
    mx = level

    def file_analysis_level(self, value: int) -> SevenzipOptions:
        """Sets level of file analysis

        .. code::
            yx=[0 | 1 | 3 | 5 | 7 | 9 ]

        =========   =====================================================
        Level       Description
        ---------   -----------------------------------------------------
        0           No analysis.
        1 or more   WAV file analysis (for Delta filter).
        7 or more   EXE file analysis (for Executable filters).
        9 or more   analysis of all files (Delta and executable filters).
        =========   =====================================================

        Default level is 5: "yx=5".

        "yx" works as "yx=9".

        If the level of analysis is smaller than 9, 7-Zip analyses only files
        that have some file name extensions: EXE, DLL, WAV.
        7-Zip reads small data block at the beginning of file and tries to
        parse the header.
        It supports only some formats: WAV, PE, ELF, Mach-O.
        Then it can select filter that can increase compression ratio for that
        file.

        By default 7-Zip uses x86 filters (BCJ or BCJ2) for PE files (EXE, DLL).
        7-Zip doesn't use analysis in default (yx=5) mode.
        If (yx=7), then analysis is used for PE files, and it can increase
        compression ratio for files for non-x86 platforms like ARM.
        """
        self['myx'] = value
        return self
    myx = file_analysis_level

    def solid(self, value: T.Union[bool, str]) -> SevenzipOptions:
        """Enables or disables solid mode. The default mode is s=on.

        .. code::
            s=[off | on | [e] [{N}f] [{N}b | {N}k | {N}m | {N}g | {N}t)]

        In solid mode, files are grouped together.
        Usually, compressing in solid mode improves the compression ratio.

        ================================ ======================================
        e                                Use a separate solid block for each
                                         new file extension.
                                         You need to use qs option also.
        {N}f                             Set the limit for number of files in
                                         one solid block
        {N}b | {N}k | {N}m | {N}g | {N}t Set a limit for the total size of a
                                         solid block in
                                         bytes / KiB / MiB / GiB / TiB.
        ================================ ======================================

        These are the default limits for the solid block size:

        =================   ================
        Compression Level   Solid block size
        -----------------   ----------------
        Store               0 B
        Fastest             16 MB
        Fast                128 MB
        Normal              2 GB
        Maximum             4 GB
        Ultra               4 GB
        =================   ================

        Limitation of the solid block size usually decreases compression ratio
        but gives the following advantages:

        - Decreases losses in case of future archive damage.
        - Decreases extraction time of a group of files (or just one file),
          so long as the group doesn't contain the entire archive.

        The updating of solid .7z archives can be slow,
        since it can require some recompression.
        """
        if isinstance(value, bool):
            value = 'on' if value else 'off'
        self['ms'] = value
        return self
    ms = solid

    def sort(self, value: bool) -> SevenzipOptions:
        """Enables or disables sorting files by type in solid archives.
        The default mode is qs=off.

        .. code::
            qs=[off | on]

        Old versions of 7-Zip (before version 15.06) used file sorting "by type"
        ("by extension").

        New versions of 7-Zip (starting from version 15.06) support two sorting
        orders:

        - qs- : sorting by name : it's default order.
        - qs : sorting by type (by file extension).

        You can get big difference in compression ratio for different sorting
        methods, if dictionary size is smaller than total size of files.
        If there are similar files in different folders,
        the sorting "by type" can provide better compression ratio in some
        cases.

        Note that sorting "by type" has some drawbacks.
        For example, NTFS volumes use sorting order "by name",
        so if an archive uses another sorting, then the speed of some
        operations for files with unusual order can fall on HDD devices
        (HDDs have low speed for "seek" operations).

        If "qs" mode provides much better compression ratio than default
        "qs-" mode, you still can increase compression ratio for "qs-" mode by
        increasing of dictionary size.

        If you think that unusual file order is not problem for you,
        and if better compression ratio with small dictionary is more important
        for you, use "qs" mode.

        Note: There are some files (for example, executable files),
        that are compressed with additional filter.
        7-Zip can't use different compression methods in one solid block,
        so 7-zip can create several groups of files that don't follow "by name"
        order in "qs-" mode, but files inside each group are still sorted by
        name in "qs-" mode.
        """
        self['mqs'] = 'on' if value else 'off'
        return self
    mqs = sort

    def filter(
        self, value: T.Union[bool, CompressionFilter]
    ) -> SevenzipOptions:
        """Enables or disables compression filters.

        The default mode is f=on, when 7-zip uses filter only for executable
        files: dll, exe, ocx, sfx, sys.
        It uses BCJ2 filter in Ultra mode and BCJ filter in other modes.
        If f=FilterID if specified, 7-zip uses specified filter for all files.
        FilterID can be: Delta:{N}, BCJ, BCJ2, ARM, ARMT, IA64, PPC, SPARC.
        """
        if isinstance(value, bool):
            value = 'on' if value else 'off'
        self['mf'] = value.name
        return self
    mf = filter

    def header_compression(self, value: bool) -> SevenzipOptions:
        """Enables or disables archive header compressing.
        The default mode is hc=on.

        .. code::
            hc=[off | on]

        If archive header compressing is enabled, the archive header will be
        compressed with LZMA method.
        """
        self['mhc'] = 'on' if value else 'off'
        return self
    mhc = header_compression

    def header_encryption(self, value: bool) -> SevenzipOptions:
        """Enables or disables archive header encryption.
        The default mode is he=off.

        .. code::
            he=[off | on]
        """
        self['mhe'] = 'on' if value else 'off'
        return self
    mhe = header_encryption

    def multithreading(self, value: T.Union[bool, int]) -> SevenzipOptions:
        """Sets multithread mode.

        .. code::
            mt=[off | on | {N}]

        If you have a multiprocessor or multicore system,
        you can get a increase with this switch.
        7-Zip supports multithread mode only for LZMA / LZMA2 compression and
        BZip2 compression / decompression.
        If you specify {N}, for example mt=4, 7-Zip tries to use 4 threads.
        LZMA compression uses only 2 threads.
        """
        if isinstance(value, bool):
            value = 'on' if value else 'off'
        self['mmt'] = value
        return self
    mmt = multithreading


_default_exclude = {'r!"desktop.ini"', 'r!"thumbs.db*"'}
_obmod_specific = {'r!"*.ini"', 'r!"*.esm"', 'r!"*.esp"'}
_PRESETS = {
    # Base presets
    'store': SevenzipOptions(
        {'t': 'zip', 'mx': 0, 'mcu': 'on', 'x': _default_exclude.copy()},
    ),
    'normal': SevenzipOptions(
        {'t': 'zip', 'mx': 5, 'mcu': 'on', 'x': _default_exclude.copy()},
    ),
    'fastest': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 1,
            'mmt': 'on',
            'x': _default_exclude.copy()
        },
    ),
    'fast': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 3,
            'mmt': 'on',
            'x': _default_exclude.copy()
        },
    ),
    'normal-7z': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 5,
            'mmt': 'on',
            'ms': '512m',
            'x': _default_exclude.copy(),
        },
    ),
    'maximum': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 7,
            'mmt': 'on',
            'ms': '1g',
            'x': _default_exclude.copy(),
        },
    ),
    'ultra': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 9,
            'mmt': 'on',
            'ms': '2g',
            'x': _default_exclude.copy(),
        },
    ),
    'extreme': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 9,
            'mmt': 2,
            'x': _default_exclude.copy(),
        },
    ).methods(
        LZMA2Method({'d': 29}),
    ),

    # Mix-in's
    '.qs': SevenzipOptions({'mqs': 'on'}),
    '.e1g': SevenzipOptions({'mqs': 'on', 'ms': 'e1g'}),
    '.e2g': SevenzipOptions({'mqs': 'on', 'ms': 'e2g'}),
    '.e4g': SevenzipOptions({'mqs': 'on', 'ms': 'e4g'}),
    '.mt': SevenzipOptions({'mmt': 'on'}),
    '.mt2': SevenzipOptions({'mmt': 2}),
    '.mt4': SevenzipOptions({'mmt': 4}),
    '.mt8': SevenzipOptions({'mmt': 8}),

    # Very specific usage below
    'obmod-pass1': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 9,
            'ms': '1g',
            'x': _default_exclude | _obmod_specific,
        },
    ),
    'obmod-pass2': SevenzipOptions(
        {
            't': '7z',
            'slp': '',
            'mx': 9,
            'ms': 'off',
            'x': {'r!"*"'},
            'i': _obmod_specific,
        },
    ),
}
available_presets: T.List[str] = sorted(list(set(_PRESETS.keys())))


def _merge_presets(presets: T.Iterable[str]) -> dict:
    opts = {}
    for preset in presets:
        opts.update(preset)
    return opts

def _list_switches(opts: dict) -> T.Sequence[str]:
    switches = []
    for key, value in opts.items():
        if isinstance(value, str):
            switches.append(key + value)
        elif hasattr(value, '__iter__'):
            switches.extend(key + v for v in value)
    return switches

def preset(name: str) -> SevenzipOptions:
    """Get a copy of preset associated with the name."""
    return _PRESETS[name].copy()

class Sevenzip(object):
    """Represents a set of options to perform a job.

    Since this is merely a wrapper around subprocess and not a programmatic
    7-Zip library, this is *not* about a single file.
    Once created, this can operate on multiple archive files with the given
    options, not bound to any particular archive, even the one specified in the
    constructor.
    """
    executable: T.Union[str, None] = _locate()
    executable_gui: T.Union[str, None] = _locate_auxiliary(
        executable, '7zG.exe'
    )
    executable_fm: T.Union[str, None] = _locate_auxiliary(
        executable, '7zFM.exe'
    )
    _allowed_switches: dict = {
        'add': {'i', 'm', 'p', 'r', 'sdel', 'sfx', 'si', 'sni', 'sns',
                'so', 'spf', 'ssw', 'stl', 't', 'u', 'v', 'w', 'x'},
        # 'list': {'ai', 'an', 'ax', 'i', 'slt', 'sns', 'p', 'r', 't', 'x'},
        # Setting default -t switch for list is annoying.
        'list': {'ai', 'an', 'ax', 'i', 'slt', 'sns', 'p', 'r', 'x'},
        'extract': {'ai', 'an', 'ao', 'ax', 'i', 'm', 'o', 'p', 'r',
                    'si', 'sni', 'sns', 'so', 'spf', 't', 'x', 'y'},
        'extractall': {'ai', 'an', 'ao', 'ax', 'i', 'm', 'o', 'p', 'r',
                       'si', 'sni', 'sns', 'so', 'spf', 't', 'x', 'y'},
        'test': {'ai', 'an', 'ax', 'i', 'p', 'r', 'sns', 'x'},
    }

    archive: T.Union[str, None] = None
    option: SevenzipOptions
    presets: T.Sequence[T.Union[str, SevenzipOptions]]
    args: T.Iterable[str]
    gui: bool

    def __init__(
        self,
        archive: T.Optional[pathstr] = None,
        presets: T.Sequence[T.Union[str, SevenzipOptions]] = ['store'],
        args: T.Iterable[str] = [],
        gui: bool = (os.name == 'nt'),
    ) -> None:
        """*archive* argument if for convenience which may safely be ignored.

        :archive:
            This is a path to the archive file you want to operate on.
            For 'add' operation, it doesn't need to exist.
        :presets:
            The "preset chain". It can take several presets, or
            ``SevenzipOptions``, while those come latter will override/
            complement the former.
            The default is ``['store']``.

            To get more presets, use the ``sevenzip.preset`` function.
            To view available presets, refer to ``sevenzip.available_presets``.
        :args:
            Addtional args to the executable in the form of list.
            No validation is done to them.
            The caller is solely responsible for the outcome.
        :gui:
            Prefer GUI executable whenever appropriate. (Windows)
        """
        if self.executable is None:
            raise FileNotFoundError("7-Zip executable not found")

        if archive is not None:
            self.archive = str(archive)

        self.option = SevenzipOptions()
        for p in presets:
            if isinstance(p, str):
                p = preset(p)
            self.option.update(p)

        self.presets = presets
        self.args = args
        self.gui = gui

    def __repr__(self) -> str:
        return (
            f'{type(self).__name__}('
                f'{self.archive!r}, '
                f'{self.presets!r}, '
                f'{self.args!r}, '
                f'{self.gui!r}'
            ')'
        )

    def _ensure_archive_path(self, archive: T.Union[None, pathstr]) -> str:
        if archive is not None:
            return str(archive)
        elif self.archive is not None:
            return self.archive
        else:
            raise TypeError('missing archive argument')


    def add(
        self,
        include: T.Iterable[pathstr],
        archive: T.Optional[pathstr] = None,
        args: T.Iterable[str] = [],
    ) -> subprocess.Popen:
        """Add files to archive.

        :include:
            What files to add. They will be enclosed in double quotes.
        :archive:
            Name of the archive.
            If provided, this will overrided the one given to the constructor.
        :args:
            Addtional args to the executable in the form of list.
            No validation is done to them.
            The caller is solely responsible for the outcome.
        """
        if self.gui and self.executable_gui is not None:
            _executable = self.executable_gui
        else:
            _executable = self.executable
        _archive = self._ensure_archive_path(archive)

        spargs = [
            _executable,
            'a',
            *self.option.args(self._allowed_switches['add']),
            *self.args,
            *args,
            '--',
            _archive,
            *(str(p) for p in include),
        ]

        return subp.popen(spargs, encoding='utf-8')
    a = add

    def list(
        self,
        archive: T.Optional[pathstr] = None,
        args: T.Iterable[str] = [],
    ) -> T.Union[str, subprocess.Popen]:
        """Lists contents of archive.

        :archive:
            Name of the archive.
            If provided, this will overrided the one given to the constructor.
        :args:
            Addtional args to the executable in the form of list.
            No validation is done to them.
            The caller is solely responsible for the outcome.
        """
        _archive = self._ensure_archive_path(archive)
        if self.gui and self.executable_fm is not None:
            _executable = self.executable_fm
            return subp.popen([_executable, _archive])
        else:
            _executable = self.executable

        spargs = [
            _executable,
            'l',
            *self.option.args(self._allowed_switches['list']),
            *self.args,
            *args,
            '--',
            _archive,
        ]

        result = subprocess.run(
            spargs, stdout=subprocess.PIPE, encoding='utf-8'
        )
        return result.stdout
    l = list

    def extract(
        self,
        output: pathstr = os.curdir,
        include: T.Iterable[pathstr] = [],
        archive: T.Optional[pathstr] = None,
        args: T.Iterable[str] = [],
    ):
        """Extracts files from an archive to the current directory or to the
        output directory.

        The output directory can be specified by -o (Set Output Directory)
        switch.

        This command copies all extracted files to one directory.
        If you want extract files with full paths, you must use x
        (Extract with full paths) command.

        7-Zip will prompt the user before overwriting existing files unless the
        user specifies the -y (Assume Yes on all queries) switch.
        If the user gives a no answer, 7-Zip will prompt for the file to be
        extracted to a new filename.
        Then a no answer skips that file; or, yes prompts for new filename.

        7-Zip accepts the following responses:

        ======  =====   =======================================================
        Answer  Abbr.   Action
        ------  -----   -------------------------------------------------------
        Yes     y
        No      n
        Always  a       Assume YES for ALL subsequent queries of the same class
        Skip    s       Assume NO for ALL subsequent queries of the same class
        Quit    q       Quit the program
        ======  =====   =======================================================

        Abbreviated responses are allowed.
        """
        if self.gui and self.executable_gui is not None:
            _executable = self.executable_gui
        else:
            _executable = self.executable
        _archive = self._ensure_archive_path(archive)

        spargs = [
            _executable,
            'e',
            *self.option.args(self._allowed_switches['extract']),
            *self.args,
            *args,
            f'-o"{output}"',
            '--',
            _archive,
            *(str(p) for p in include),
        ]

        return subp.popen(spargs)
    e = extract

    def extractall(
        self,
        output: pathstr = os.curdir,
        include: T.Iterable[pathstr] = [],
        archive: T.Optional[pathstr] = None,
        args: T.Iterable[str] = [],
    ):
        """Extracts files from an archive with their full paths in the current
        directory, or in an output directory if specified.
        """
        if self.gui and self.executable_gui is not None:
            _executable = self.executable_gui
        else:
            _executable = self.executable
        _archive = self._ensure_archive_path(archive)

        spargs = [
            _executable,
            'x',
            *self.option.args(self._allowed_switches['extractall']),
            *self.args,
            *args,
            f'-o"{output}"',
            '--',
            _archive,
            *(str(p) for p in include),
        ]

        return subp.popen(spargs)
    x = extractall

    def test(
        self,
        include: T.Iterable[pathstr] = [],
        archive: T.Optional[pathstr] = None,
        args: T.Iterable[str] = [],
    ):
        """Tests archive files."""
        if self.gui and self.executable_gui is not None:
            _executable = self.executable_gui
        else:
            _executable = self.executable
        _archive = self._ensure_archive_path(archive)

        spargs = [
            _executable,
            't',
            *self.option.args(self._allowed_switches['extract']),
            *self.args,
            *args,
            '--',
            _archive,
            *(str(p) for p in include),
        ]

        return subp.popen(spargs)
    t = test
