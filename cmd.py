#! /usr/bin/env python3

import os
import shutil
import sys

from pathlib import Path
from typing import (
    Any,
    Callable,
    Container,
    Iterable,
    Iterator,
    Optional,
    Mapping,
    Sequence,
    Tuple,
    TypeVar,
    Union
)


# typedef
TV = TypeVar('TV')


# Querry

class QueryError(Exception):
    ...


def format_choices_inline(
    self, choices: Sequence[str], default: Optional[int] = None
) -> str:
    """Format choice view like `` (Y/n): ``."""
    words = []
    for idx, choice in enumerate(choices):
        words.append(choice.upper() if idx == default else choice.lower())
    return f" ({'/'.join(words)}): "


def format_choices_list(
    self, choices: Sequence[str], default: Optional[int] = None
) -> str:
    """Format choice view like `` 1 . spam\n[2]. eggs\nChoice: ``"""
    lines = ['\n']
    for nth, choice in enumerate(choices, 1):
        if nth - 1 == default:
            lines.append(f'[{nth}]. {choice}')
        else:
            lines.append(f' {nth} . {choice}')
    lines.append('\nChoice: ')
    return '\n'.join(lines)


def yes_or_no(answer: str) -> Union[bool, None]:
    """Convert yes/y/no/n to bool.

    May return ``None`` if answer is unrecognizable.
    """
    answer = answer.lower()
    if answer in ('y', 'yes'):
        return True
    elif answer in ('n', 'no'):
        return False
    else:
        return None


def yes(*args, **kwargs) -> True:
    return True


class Query(object):
    """Interactive query maker for the ease of asking questions.

    ----------
    Attributes
    ----------

    :history:
        This is a list of dictionaries of *question*, *answer*, *value*
        whether answer was a valid input or not.
    :valid_history:
        This is a subset of *history* that contains only the valid answers,
        with the same keys with *history*.
    """
    question: str
    choices: Sequence[str]
    expected: Union[Container[Any], Callable[[Any], bool]]
    default: Optional[int]
    parser: Callable[[str], Any]
    choice_formatter: Callable[[Sequence[str], Optional[int]], str]
    history: Sequence[Mapping[str, Any]]
    valid_history: Sequence[Mapping[str, Any]]

    fail_message: str = '\nAnswer not understood, please try again.\n\n'

    def __init__(
        self,
        question: str,
        choices: Sequence[str],
        expected: Union[Container[Any], Callable[[Any], bool]] = yes,
        default: Optional[int] = None,
        parser: Callable[[str], Any] = str,
        choice_formatter: Callable[[Sequence[str], Optional[int]], str] \
            = format_choices_inline
    ) -> None:
        """Initialize query for a single question.

        :question:
            This will be written to stdout without newline appended.
            You may pass whatever value for this,
            as the ``Query.ask`` method also accepts ``question`` argument.
        :choices:
            This is a sequence of strings that will be displayed, highlighting
            the default value;
            How this will be highlighted depends on the formatter.
        :expected:
            List of expected *parsed* answer values,
            or a callable which can determine the parsed answer's validity.
            The answer will be parsed (through ``parser``) first,
            and the returned value will be validated through this.

            If this is any object that implements ``__contains__`` protocol,
            the parsed value is checked if it is ``in`` this container.

            If this is a callable, it should accept anything
            (that ``parser`` may return) and return its validity as either
            ``True`` or ``False``.

            If validity check fails, the question is asked again until an
            acceptable answer is finally given.
        :default:
            Numeric index of default value.
            If the user simply hit ``Enter``,
            this value will be implied as the choice.
            By default, the query has no default choice;
            Empty input is an invalid input.
        :parser:
            User's choice is passed to this callable and the return value is
            checked against ``expected``.
            Default is built-in class ``str``.
            If custom parser is specified,
            it needs to accept a string as argument.
        :choice_formatter:
            This decides how default choice highlighting is displayed.
            The default is ``format_choices_inline`` where all the choices are
            displayed in the same line (with the question) and the default
            choice is displayed UPPERCASE.

            For a less compact and more readable "list" style display,
            ``format_choices_list`` is provided.

            Custom formatter must be a callable that accepts a sequence of
            strings as its first positional argument, and the default index
            value as optional.
        """
        self.question = question
        self.choices = choices
        self.expected = expected
        self.default = default
        self.parser = parser
        self.choice_formatter = choice_formatter
        self.history = []
        self.valid_history = []

    def ask(self, question: Optional[str] = None, trials: int = -1) -> Any:
        """Ask the question and return the interpreted answer.

        :question:
            If provided, will ask with it instead of the stored question.
        :trials:
            Specifies how many times the same question will be asked.
            Default is -1, which means infinte.
            If all trials are spent and no valid answer is given,
            ``QueryError`` is raised.
        """
        if question is None:
            question = self.question

        while True:
            sys.stdout.write(question)
            sys.stdout.write(self.choice_formatter(self.choices, self.default))
            answer = input()
            value = self.parser(answer)
            self.history.append(
                {'question': question, 'answer': answer, 'value': value}
            )
            if self._validate(value):
                self.valid_history.append(
                    {'question': question, 'answer': answer, 'value': value}
                )
                return value
            elif 0 < trials:
                trials -= 1
                sys.stdout.write(self.fail_message)
            else:
                raise QueryError('Could not get a recognizable answer')

    def _validate(self, value: Any) -> bool:
        if hasattr(self.expected, '__contains__'):
            return value in self.expected
        else:
            return self.expected(value)


class YesNoQuery(Query):
    """Subclass of ``Query`` that specializes in asking simple questions."""
    choices = ('y', 'n')

    def __init__(self, question: str, default: Optional[int] = None) -> None:
        super().__init__(question, default)
        self.parser = yes_or_no
        self.expected = {True, False}


# PipeInput

class PipeInput(object):
    """Abstraction layer for easier handling of pipeline input.

    This combines the interfaces of pipe input and arg input together,
    abstracting them as a single iterator.

    It is an iterator, and also a subscribable mapping of input history.
    When iterated over, inputs from *alt* arg are yielded first,
    and then the strings from the pipeline are consumed.
    The indices are numeric, and subscribing will fetch value as
    whatever *type* specified when instanciating the object.

    :type:
        If provided, convert all input to this type. Default is ``str``.
    :alt:
        It's an alternate iterable of args when pipe inputs are not available.
        If present, these are consumed first before pipe input.
    """
    _alt: Iterator[str]
    alt: Iterable[str]
    type: Optional[Callable[..., TV]]
    _history_raw: Sequence[str]
    _history: Sequence[Union[TV, str]]
    _isatty: bool

    _cursor: int = 0
    _alt_spent: bool = False

    def __init__(
        self, type: Callable[..., TV] = str, alt: Optional[Iterable[str]] = None
    ) -> None:
        self.type = type
        if alt is None:
            alt = []
        self._alt = iter(alt)
        self.alt = list(alt)
        self._history_raw = []
        self._history = []
        self._isatty = os.isatty(sys.stdin.fileno())

    def __repr__(self):
        return (
            f'{type(self).__name__}(type={self.type}, alt={self._history_raw})'
        )

    def __iter__(self) -> Iterator[TV]:
        self._cursor = 0
        return self

    def __next__(self) -> TV:
        cursor = self._cursor
        if cursor < len(self._history):
            self._cursor += 1
            return self._history[cursor]

        # Attempt to take value from the alt args.
        if not self._alt_spent:
            try:
                value = next(self._alt)
                self._cursor += 1
                self._history_raw.append(value)
                value = self.type(value)
                self._history.append(value)
                return value
            except StopIteration:
                self._alt_spent = True

        # Finally, consume pipe input.
        if self._isatty:
            raise StopIteration
        value = sys.stdin.readline().rstrip()
        if value:
            self._cursor += 1
            self._history_raw.append(value)
            value = self.type(value)
            self._history.append(value)
            return value
        else:
            raise StopIteration

    def __contains__(self, value: str) -> bool:
        """Search with raw input."""
        return value in self._history_raw

    def __getitem__(self, idx) -> TV:
        return self._history[idx]

    def __len__(self):
        return len(self._history)

    def rewind(self, pos: int = 0) -> Iterator[TV]:
        """Rewind iteration and return the fresh self.

        :pos:
            Rewind to *pos*. Valid position must be smaller than length.
            If it's out of bound, raises ValueError.
        """
        if pos < len(self):
            self._cursor = pos
            return self
        raise ValueError('pos greater than last index')


def get_pipe() -> Sequence[str]:
    """Return contents of pipe input, removing empty lines.

    ***Note***: This collects pipe inputs hastily;
    It means this acts as a bottleneck in the pipeline.

    Also, this does not remove powershell's fields header.
    Remove them manually.
    """
    if os.isatty(sys.stdin.fileno()):
        return []
    else:
        return [arg.strip() for arg in sys.stdin.read().splitlines() if arg]


def config_stdio(**kwargs: Mapping[str, Any]) -> None:
    """Reconfigure all ``stdin``, ``stdout`` and ``stderr``.

    Passes all kwargs as provided.
    """
    sys.stdin.reconfigure(**kwargs)
    sys.stdout.reconfigure(**kwargs)
    sys.stderr.reconfigure(**kwargs)



# Files & path utils

def iter_file(paths: Iterable[Path], glob_pattern: str) -> Iterable[Path]:
    """Given paths, be it file or directory, always yield files.

    :paths:
        *paths* can either be an iterable of directories or files.
        If path is a directory, yielded files are found matching *glob_pattern*.
        If path is a file, it is always yielded regardless of pattern.
    :glob_pattern:
        The pattern is applied through ``Path.glob`` method.
        If recursion is required, preprend(join) ``'**/'`` before it.
    """
    for path in paths:
        if path.is_dir():
            yield from path.glob(glob_pattern)
        elif path.is_file():
            yield path
        else:
            raise FileNotFoundError(str(path))


def path_exists(path: Path, warn: bool = True) -> bool:
    """Test if *path* exists, return existence state, warn if not found.

    This function is intended to use with pipes.
    :warn:
        If ``True``, write warning to stdout.
    """
    if path.exists():
        return True
    else:
        sys.stdout.write(f'Warning: "{str(path)}" not found\n')
        return False



# Miscellaneous

def limit_string(
    full: str,
    width: Union[int, float, str] = 'auto',
    tail: bool = True,
    pad: bool = True,
    justify: str = 'left',
) -> str:
    """Limit length of string to *width*.

    :full:
        The full content of the string.
    :width:
        The returned string will have this much width at maximum.
        If this is a float, it must be a fraction of the width of the terminal.
        Default is ``'auto'``; Starting from 20 at 80 terminal width,
        it changes by 1 every 2 unit change of terminal width,
        while guaranteeing at least 10 spaces for the string.
    :tail:
        Default ``True``. If ``True``, middle part of the *full* string will
        be ``'...'`` and the rest are the tail of *full*.
        If ``False``, the tail part will be discarded.
    :pad:
        Default is ``True``.
        If *full* is shorter than *width*, fill the rest with space.
    :justify:
        One of ``'left'``, ``'center'``, ``'right'``. Default is ``'left'``.
        Indicates the alignment of string when it's shorter than *width*.
    """
    if isinstance(width, int):
        _width = width
    else:
        term_width = shutil.get_terminal_size().columns
        if width == 'auto':
            _width = max(10, 20 + (term_width - 80)//2)
        else:
            _width = round(term_width / width)
    padlen = _width - len(full)
    if padlen >= 0:
        if pad:
            if justify == 'left':
                return full + ' '*padlen
            elif justify == 'right':
                return ' '*padlen + full
            elif justify == 'center':
                return ' '*(padlen // 2) + full + ' '*round(padlen / 2)
            else:
                raise ValueError("Unknown alignment")
        return full
    if tail:
        rest = _width - 3
        return full[:round(rest / 2)] + '...' + full[-(rest // 2):]
    else:
        return full[:_width - 3] + '...'
