"""
Custom configparser section/option reference syntax for the diff-file option.

diff-file supports a "section reference" syntax for it's value:

    [mirror]
    ...
    diff-file = /folder{{ <SECTION>_<OPTION> }}/more

<SECTION> matches a configparser section and <OPTION> matches an option in that section.
The portion of the diff-file value delimited with {{ and }} is replaced with the
value from the specified option, which should be a string.
"""

import re
from configparser import ConfigParser, NoOptionError, NoSectionError

# Pattern to check if a string contains a custom section reference
_REF_PAT = r".*\{\{.+_.+\}\}.*"

# Pattern to decompose a custom section reference into parts
_REF_COMPONENT_PAT = r"""
    # capture everything from start-of-line to the opening '{{' braces into group 'pre'
    ^(?P<pre>.*)\{\{
    # restrict section names to ignore surrounding whitespace (different from
    # configparser's default SECTRE) and disallow '_' (since that's our separator)
    \s*
    (?P<section>[^_\s](?:[^_]*[^_\s]))
    # allow (but ignore) whitespace around the section-option delimiter
    \s*_\s*
    # option names ignore surrounding whitespace and can include any character, but
    # must start and end with a non-whitespace character
    (?P<option>\S(?:.*\S)?)
    \s*
    # capture from the closing '}}' braces to end-of-line into group 'post'
    \}\}(?P<post>.*)$
"""


def has_config_reference(value: str) -> bool:
    return re.match(_REF_PAT, value) is not None


def eval_config_reference(config: ConfigParser, value: str) -> str:
    match_result = re.match(_REF_COMPONENT_PAT, value, re.VERBOSE)

    if match_result is None:
        raise ValueError(f"Unable to parse config option reference from '{value}'")

    pre, sect_name, opt_name, post = match_result.group(
        "pre", "section", "option", "post"
    )

    try:
        ref_value = config.get(sect_name, opt_name)
        return pre + ref_value + post
    except (NoSectionError, NoOptionError) as exc:
        raise ValueError(exc.message)
