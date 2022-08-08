#! /usr/bin/env python3

"""This module is an OOP wrapper around the standard library *heapq*."""

import heapq
import typing as T


class Heap(object):
    """An OOP wrapper around standard library *heapq* for convenience.

    All methods are provided without modification.
    Previously module-level functions are bundled into this class as static
    methods.
    Docstrings are copied as well.
    """
    list: list

    def __init__(self, iterable: T.Iterable = []) -> None:
        self.list = iterable.copy()
        heapq.heapify(self.list)

    def push(self, item):
        heapq.heappush(self.list, item)

    def pop(self):
        return heapq.heappop(self.list)

    def pushpop(self, item):
        return heapq.heappushpop(self.list, item)

    def replace(self, item):
        return heapq.heapreplace(self.list, item)

    @staticmethod
    def merge(*iterables, key=None, reverse=False) -> T.Iterator:
        return heapq.merge(*iterables, key=key, reverse=reverse)

    @staticmethod
    def nlargest(n: int, iterable: T.Iterable, key=None) -> list:
        return heapq.nlargest(n, iterable, key=key)

    @staticmethod
    def nsmallest(n: int, iterable: T.Iterable, key=None) -> list:
        return heapq.nsmallest(n, iterable, key=key)

    # Copypasta of original docstrings
    __init__.__doc__ = __init__.push.__doc__
    push.__doc__ = heapq.push.__doc__
    pop.__doc__ = heapq.pop.__doc__
    pushpop.__doc__ = heapq.pushpop.__doc__
    replace.__doc__ = heapq.replace.__doc__
    merge.__doc__ = heapq.merge.__doc__
    nlargest.__doc__ = heapq.nlargest.__doc__
    nsmallest.__doc__ = heapq.nsmallest.__doc__
