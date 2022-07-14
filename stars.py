#! /usr/bin/env python3

"""This module provides ease-of-use starstarmap decorators.

>>> from itertools import starmap
>>> iargs = [[1, 2], [3, 4]]
>>> ikwargs = [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
>>>
>>> list(starstar(map)(_test_echo, iargs, ikwargs))
["(1, 2), {'a': 1, 'b': 2}", "(3, 4), {'a': 3, 'b': 4}"]
>>>
>>> list(star(starmap)(_test_echo, iargs, ikwargs))
["(1, 2), {'a': 1, 'b': 2}", "(3, 4), {'a': 3, 'b': 4}"]

"""

import typing as T

from itertools import repeat


def _starstar(arg):
    func, args, kwargs = arg
    return func(*args, **kwargs)

def _star(func, args, kwargs):
    return func(*args, **kwargs)

def stars(num_stars: int) -> T.Callable:
    """Meta-decorator to supply the kind of source mapper function.

    This generates decorator around [star]map to make them accept kwargs.
    for example, built-in *map* demands iterables of iterables,
    each holding one kind of positional arguments.
    ``itertools.starmap`` can take care of arg-arranging nightmare,
    but you still can't pass kwargs, especially keyword-only arguments.

    The generated starstar(** around map) or star(* around *map) can make them
    accept keyword arguments,
    as well as keeping intuitive way of arranging of arguments.

    .. code:: python
        from itertools import starmap
        from semper.stars import stars, star, starstar

        ssmap_2 = star(starmap)   # @stars(1) == @star
        ssmap_1 = starstar(map)   # @stars(2) == @starstar

    :num_stars:
        Must be 1 or 2. This indicates the number of stars to 'prepend'.
    """
    if num_stars == 1:
        wrapper = _star
    elif num_stars == 2:
        wrapper = _starstar

    def _mapmaker(mapper: T.Callable) -> T.Callable:
        def _map(
            func: T.Callable,
            iargs: T.Iterable[T.Sequence],
            ikwargs: T.Iterable[T.Mapping[str, T.Any]],
            **kwargs: T.Mapping[str, T.Any],
        ) -> T.Iterable:
            starmap_args = zip(repeat(func), iargs, ikwargs)
            return mapper(wrapper, starmap_args, **kwargs)
        return _map

    return _mapmaker

star = stars(1)
starstar = stars(2)


def _test_echo(*args, **kwargs):
    return f'{args}, {kwargs}'


if __name__ == '__main__':
    import doctest
    doctest.testmod()
