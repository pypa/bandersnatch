from collections.abc import Callable
from configparser import ConfigParser
from typing import Any, TypeAlias, TypeVar

import attrs
from attrs import Attribute

from . import errors

AttrsConverter: TypeAlias = Callable[[Any], Any]
AttrsFieldTransformer: TypeAlias = Callable[[type, list[Attribute]], list[Attribute]]

_V = TypeVar("_V")
AttrsValidator: TypeAlias = Callable[[Any, Attribute, _V], _V]


def only_if_str(converter_fn: AttrsConverter) -> AttrsConverter:
    """Wrap an attrs converter function so it is only applied to strings.

    'converter' functions on attrs fields are applied to all values set to the field,
    *including* the default value. This causes problems if the default value is already
    the desired type but the converter only handles strings.

    :param AttrsConverter converter_fn: any attrs converter
    :return AttrsConverter: converter function that uses `converter_fn` if the passed
        value is a string, and otherwise returns the value unmodified.
    """

    def _apply_if_str(value: Any) -> Any:
        if isinstance(value, str):
            return converter_fn(value)
        else:
            return value

    return _apply_if_str


def get_name_value_for_option(
    config: ConfigParser, section_name: str, option: Attribute
) -> tuple[str, object | None]:
    option_name = config.optionxform(option.alias or option.name)

    if option.default is attrs.NOTHING and not config.has_option(
        section_name, option_name
    ):
        raise errors.MissingOptionError.for_option(section_name, option_name)

    getter: Callable[..., Any]
    if option.converter is not None:
        getter = config.get
    elif option.type == bool:
        getter = config.getboolean
    elif option.type == float:
        getter = config.getfloat
    elif option.type == int:
        getter = config.getint
    else:
        getter = config.get

    try:
        option_value = getter(section_name, option_name, fallback=None)
    except ValueError as conversion_error:
        type_name = option.type.__name__ if option.type else "???"
        message = f"can't convert option name '{option_name}' to expected type '{type_name}': {conversion_error!s}"
        raise errors.InvalidValueError.for_option(
            section_name, option_name, message
        ) from conversion_error

    return option_name, option_value


validate_not_empty: AttrsValidator = attrs.validators.min_len(1)
