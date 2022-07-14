# semper

My python profile-something, intended for trivial, everyday uses.

At first this was named 'everyday'.
Then I thought it's a bit much of typing, so renamed it 'semper'.
And then again I discovered that the name 'daily' is even shorter.
But can't change now. (Doh!)


## Description

This is part of my kinda-sorta python profile, but pushed to git anyway for
easier management and code backup purposes.

The codes are written for my own everyday usage, hence the name "semper".
Some are plain nonsenses, some I can't find any use for anyone else but me,
some may actually be somewhat useful.


## Plans

Someday, I gotta make an awesome Sphinx doc for this.
I need documentation myself.


## Dependencies

pipe


## Modules

As the codes have been there for a long time and I add new things and delete
things on a whim, the packcage's structure is in total mayhem.
Often nothing can be done about it as it can break backward-compatibility.


### cmd

It's a collection of tools uses for quick cli programs that I seem to produce
on a weekly basis (and promptly discarded after its purpose served).

### pipes

Custom pipes extended from those of the `pipe` package.
Only marginally useful for shell-like interpreter usage.

### stars

The module provides two decorators, `star` and `starstar`, to convert map- or
starmap-like function to a "starstarmap" which can accept *kwargs*,
as long as the function's interface is identical to the built-in `map` or
`itertools.starmap`.

### dtypes

- cistr: case insensitive string class `CaseInsensitiveString` and
  `NormCasedString`. They can be somewhat useful when you have to handle a lot
  of paths and your program must run both on Windows and Unix.
  For example, they can be used as dict keys.

### sh

Now the real weird things. Few of them will make sense as a programming api,
because most of them implement that aren't very worth implementing, and some of
them even use freaking `argparse` function-wise.

It's all to reduce typings, though. It can be good when you're butthurt about
your system shell, both sh and powsh, or just want a strong control that python
can offer, and use python interpreter like shell.
Function-wise argparsing and functional pipes are good for that.
Otherwise, it doesn't make too much sense to have them around.

- hash: Let's you produce GNU coreutils style checksum format on Windows.
  Normally on powsh you need like 3 lines of typing to output checksums in
  coreutils format.
  (And even moar typing to get `Get-FileHash` check with those outputs)

- sevenzip: It's a commandline wrapper for 7-Zip as I use it a lot.
  Things found in PyPI just aren't too satisfactory, although I have no doubt
  they provide much cleaner programming-like interface.
  (Except that you can't fine-tune options there)
