#! /usr/bin/env python3

"""This module provides useful derivations of primitive types."""

import os
import typing as T

from collections import UserString


class CaseInsensitiveString(UserString):
    """Subclass of ``UserString`` that does case-insensitive comparison.
    The primary purpose is to perform case-insensitive file manipulation.

    This stores the 'face' value as well as the underlying normalized value.
    Exactly under what circumstances are case-insensitive tests done is
    described below.

    - hashing is done with the normalized version.
    - The *in* operator does case-insensitive comparison as well.
    - However, case-insensitive equality test is done only if the other
      operand is an instance of this as well.
      That is, comparison with plain string is done 'their' way,
      so that you would not be confused.

    Caution:
        Since this hashes itself with everything lowercased,
        storing them and the ordinary strings in the same dictionary
        might not be the smartest idea, since there'll be a lot of collisions.

    Examples:
        ```
        >>> a = CaseInsensitiveString('aBcDe12345')
        >>> b = CaseInsensitiveString('AbCdE12345')
        >>> repr(a)
        "CaseInsensitiveString('abcde12345')"
        >>> print(a)
        aBcDe12345
        >>> hash(a) == hash('aBcDe12345'.casefold())
        True
        >>> 'b' in a
        True
        >>> 'aBcDe12345' == a
        True
        >>> 'AbCdE12345' == a
        False
        >>> a == b
        True
        >>> isinstance(a + b, CaseInsensitiveString)
        True
        >>> print(a + b)
        aBcDe12345AbCdE12345

        ```
    """
    _data: str

    def __init__(self, seq: T.Any) -> None:
        super().__init__(seq)
        self._data = self._casefold(self.data)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._data!r})'

    def __hash__(self) -> int:
        return hash(self._data)

    def __contains__(self, char: str) -> bool:
        return self._casefold(char) in self._data

    def __eq__(self, other: str) -> bool:
        """Do case-insensitive only when the other is cistr as well."""
        if isinstance(other, type(self)):
            return other._data == self._data
        else:
            return other == self.data

    def _casefold(self, value: str) -> str:
        return value.casefold()


class NormCasedString(CaseInsensitiveString):
    """Subclass of ``CaseInsensitiveString`` that uses ``os.path.normcase``
    for casefolding.
    """
    def _casefold(self, value: str) -> str:
        return os.path.normcase(value)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
