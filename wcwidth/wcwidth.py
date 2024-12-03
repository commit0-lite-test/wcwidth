"""Python implementation of wcwidth() and wcswidth().

https://github.com/jquast/wcwidth

From Markus Kuhn's C code, retrieved from:

    http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c

An implementation of wcwidth() and wcswidth() (defined in
IEEE Std 1002.1-2001) for Unicode.

http://www.opengroup.org/onlinepubs/007904975/functions/wcwidth.html
http://www.opengroup.org/onlinepubs/007904975/functions/wcswidth.html

In fixed-width output devices, Latin characters all occupy a single
"cell" position of equal width, whereas ideographic CJK characters
occupy two such cells. Interoperability between terminal-line
applications and (teletype-style) character terminals using the
UTF-8 encoding requires agreement on which character should advance
the cursor by how many cell positions. No established formal
standards exist at present on which Unicode character shall occupy
how many cell positions on character terminals. These routines are
a first attempt of defining such behavior based on simple rules
applied to data provided by the Unicode Consortium.

For some graphical characters, the Unicode standard explicitly
defines a character-cell width via the definition of the East Asian
FullWidth (F), Wide (W), Half-width (H), and Narrow (Na) classes.
In all these cases, there is no ambiguity about which width a
terminal shall use. For characters in the East Asian Ambiguous (A)
class, the width choice depends purely on a preference of backward
compatibility with either historic CJK or Western practice.
Choosing single-width for these characters is easy to justify as
the appropriate long-term solution, as the CJK practice of
displaying these characters as double-width comes from historic
implementation simplicity (8-bit encoded characters were displayed
single-width and 16-bit ones double-width, even for Greek,
Cyrillic, etc.) and not any typographic considerations.

Much less clear is the choice of width for the Not East Asian
(Neutral) class. Existing practice does not dictate a width for any
of these characters. It would nevertheless make sense
typographically to allocate two character cells to characters such
as for instance EM SPACE or VOLUME INTEGRAL, which cannot be
represented adequately with a single-width glyph. The following
routines at present merely assign a single-cell width to all
neutral characters, in the interest of simplicity. This is not
entirely satisfactory and should be reconsidered before
establishing a formal standard in this area. At the moment, the
decision which Not East Asian (Neutral) characters should be
represented by double-width glyphs cannot yet be answered by
applying a simple rule from the Unicode database content. Setting
up a proper standard for the behavior of UTF-8 character terminals
will require a careful analysis not only of each Unicode character,
but also of each presentation form, something the author of these
routines has avoided to do so far.

http://www.unicode.org/unicode/reports/tr11/

Latest version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""

from __future__ import division
import os
import sys
import warnings
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .unicode_versions import list_versions

try:
    from functools import lru_cache
except ImportError:
    # If this import fails, you may need to install the backports.functools_lru_cache package
    from backports.functools_lru_cache import lru_cache
_PY3 = sys.version_info[0] >= 3

# Type annotations for global variables
WIDE_EASTASIAN: list[tuple[int, int]]
VS16_NARROW_TO_WIDE: dict[int, int]


def _bisearch(ucs: int, table: list[tuple[int, int]]) -> int:
    """Auxiliary function for binary search in interval table.

    Args:
    ----
        ucs: Ordinal value of unicode character.
        table: List of starting and ending ranges of ordinal values.

    Returns:
    -------
        1 if ordinal value ucs is found within lookup table, else 0.

    """
    if not table or ucs < table[0][0] or ucs > table[-1][1]:
        return 0

    lbound = 0
    ubound = len(table) - 1

    while ubound >= lbound:
        mid = (lbound + ubound) // 2
        if ucs > table[mid][1]:
            lbound = mid + 1
        elif ucs < table[mid][0]:
            ubound = mid - 1
        else:
            return 1

    return 0


@lru_cache(maxsize=1000)
def wcwidth(wc: str, unicode_version: str = "auto") -> int:
    r"""Given one Unicode character, return its printable length on a terminal.

    Args:
    ----
        wc: A single Unicode character.
        unicode_version: A Unicode version number, such as
            ``'6.0.0'``. A list of version levels suported by wcwidth
            is returned by :func:`list_versions`.

            Any version string may be specified without error -- the nearest
            matching version is selected.  When ``auto`` (default), the
            highest Unicode version level is used.

    Returns:
    -------
        The width, in cells, necessary to display the character of
        Unicode string character, ``wc``.  Returns 0 if the ``wc`` argument has
        no printable effect on a terminal (such as NUL '\0'), -1 if ``wc`` is
        not printable, or has an indeterminate effect on the terminal, such as
        a control character.  Otherwise, the number of column positions the
        character occupies on a graphic terminal (1 or 2) is returned.

    See :ref:`Specification` for details of cell measurement.

    """
    # Ensure wc is a single character
    if not isinstance(wc, str) or len(wc) != 1:
        return -1

    ucs = ord(wc)

    # NULL character
    if ucs == 0:
        return 0

    # C0/C1 control characters
    if ucs < 32 or 0x07F <= ucs < 0x0A0:
        return -1

    # Use the latest unicode version if set to "auto"
    if unicode_version == "auto":
        unicode_version = max(ZERO_WIDTH.keys())

    # Ensure unicode_version is a valid key
    valid_versions = list(ZERO_WIDTH.keys())
    if unicode_version not in valid_versions:
        unicode_version = max(v for v in valid_versions if v <= unicode_version)

    # Check for zero width characters
    if _bisearch(ucs, ZERO_WIDTH[unicode_version]):
        return 0

    # Check for emoji sequences and ZWJ sequences
    if 0x1F000 <= ucs <= 0x1FFFF:
        return 2  # Emoji characters have width 2
    if ucs == 0x200D:  # Zero Width Joiner
        return 0

    # Check for wide East Asian characters
    if _bisearch(ucs, WIDE_EASTASIAN[unicode_version]):
        return 2

    # Check for variation selectors
    if 0xFE00 <= ucs <= 0xFE0F:
        return 0

    # Check for VS16 characters
    if ucs in VS16_NARROW_TO_WIDE:
        return 2

    # Special case for FEMALE SIGN and MALE SIGN
    if ucs in (0x2640, 0x2642) and unicode_version >= '9.0.0':
        return 2

    # All other characters are considered single width
    return 1


def wcswidth(pwcs: str, n: int | None = None, unicode_version: str = "auto") -> int:
    """Given a unicode string, return its printable length on a terminal.

    Args:
    ----
        pwcs: Measure width of given unicode string.
        n: When ``n`` is None (default), return the length of the entire
            string, otherwise only the first ``n`` characters are measured. This
            argument exists only for compatibility with the C POSIX function
            signature. It is suggested instead to use python's string slicing
            capability, ``wcswidth(pwcs[:n])``
        unicode_version: An explicit definition of the unicode version
            level to use for determination, may be ``auto`` (default), which uses
            the Environment Variable, ``UNICODE_VERSION`` if defined, or the latest
            available unicode version, otherwise.

    Returns:
    -------
        The width, in cells, needed to display the first ``n`` characters
        of the unicode string ``pwcs``.  Returns ``-1`` for C0 and C1 control
        characters!

    See :ref:`Specification` for details of cell measurement.

    """
    if n is None:
        n = len(pwcs)

    width = 0
    i = 0
    while i < n:
        char = pwcs[i]
        char_width = wcwidth(char, unicode_version)
        
        # Handle emoji sequences
        if 0x1F000 <= ord(char) <= 0x1FFFF:
            # Look ahead for ZWJ sequences
            j = i + 1
            while j < n and (ord(pwcs[j]) == 0x200D or 0x1F000 <= ord(pwcs[j]) <= 0x1FFFF or 0xFE00 <= ord(pwcs[j]) <= 0xFE0F):
                j += 1
            width += 2  # Count the entire emoji sequence as width 2
            i = j
            continue

        if char_width < 0:
            return -1
        width += char_width
        i += 1

    return width


@lru_cache(maxsize=128)
def _wcversion_value(ver_string: str) -> tuple[int, ...]:
    """Integer-mapped value of given dotted version string.

    Args:
    ----
        ver_string: Unicode version string, of form ``n.n.n``.

    Returns:
    -------
        Tuple of digit tuples, ``tuple(int, [...])``.

    """
    return tuple(map(int, ver_string.split(".")))


@lru_cache(maxsize=8)
def _wcmatch_version(given_version: str) -> str:
    """Return nearest matching supported Unicode version level.

    If an exact match is not determined, the nearest lowest version level is
    returned after a warning is emitted.  For example, given supported levels
    ``4.1.0`` and ``5.0.0``, and a version string of ``4.9.9``, then ``4.1.0``
    is selected and returned:

    >>> _wcmatch_version('4.9.9')
    '4.1.0'
    >>> _wcmatch_version('8.0')
    '8.0.0'
    >>> _wcmatch_version('1')
    '4.1.0'

    Args:
    ----
        given_version: Given version for compare, may be ``auto``
            (default), to select Unicode Version from Environment Variable,
            ``UNICODE_VERSION``. If the environment variable is not set, then the
            latest is used.

    Returns:
    -------
        Unicode string, or non-unicode ``str`` type for python 2
        when given ``version`` is also type ``str``.

    """
    if given_version == "auto":
        given_version = os.environ.get("UNICODE_VERSION", "latest")

    if given_version == "latest":
        return list_versions()[-1]

    supported_versions = list_versions()
    
    try:
        given_value = _wcversion_value(given_version)
    except ValueError:
        warnings.warn(f"Invalid Unicode version {given_version}, using latest")
        return supported_versions[-1]

    for version in reversed(supported_versions):
        if _wcversion_value(version) <= given_value:
            if version != given_version:
                if _wcversion_value(version) < given_value:
                    warnings.warn(
                        f"Unicode version {given_version} not found, using {version}"
                    )
            return version

    # If no suitable version found, return the earliest supported version
    warnings.warn(
        f"Unicode version {given_version} not found, using {supported_versions[0]}"
    )
    return supported_versions[0]
