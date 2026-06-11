"""`blackboxprotobuf.lib.api` 模块提供了用于解码和重新编码 protobuf 消息的高级函数。

大多数函数接收输入数据、类型定义和配置对象。

'message_type' 或类型定义（typedef）是 blackboxprotobuf 特定的格式，
用于定义每个字段解码/编码时应使用的类型。
解码函数中是可选的，但编码函数中必须提供。
解码函数会返回一个 typedef，该 typedef 用于重新编码消息。
如果在解码时提供了 typedef，则会使用这些类型进行解码，
返回的 typedef 将是原始 typedef 加上消息中任何新字段的组合。

config 参数来自 `blackboxprotobuf.lib.config` 的 Config 对象，
允许重新配置默认类型，并存储可在其他 typedef 中引用的"已知"消息 typedef。
可以省略此参数以使用默认的共享配置对象。
"""

# 版权所有 (c) 2018-2024 NCC Group Plc
#
# 特此免费授予任何获得本软件及相关文档文件（“软件”）副本的人，不受限制地处理
# 本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或
# 销售本软件副本的权利，并允许获得本软件的人这样做，但须符合以下条件：
#
# 上述版权声明和本许可声明应包含在本软件的所有副本或实质性部分中。
#
# 本软件按“原样”提供，不作任何明示或暗示的担保，包括但不限于对适销性、特定
# 用途适用性和非侵权的担保。在任何情况下，作者或版权持有人均不对因使用本软件
# 而产生的任何索赔、损害或其他责任承担责任，无论是合同行为、侵权行为还是其他
# 行为。

import re
import six
import json
import collections
import blackboxprotobuf.lib.protofile
import blackboxprotobuf.lib.types.length_delim
import blackboxprotobuf.lib.types.type_maps
from blackboxprotobuf.lib.config import default as default_config
from blackboxprotobuf.lib.exceptions import (
    TypedefException,
    EncoderException,
    DecoderException,
)
from blackboxprotobuf.lib.typedef import TypeDef

if six.PY3:
    import typing

    # 如果不在这里检查，Config 会有循环导入
    if typing.TYPE_CHECKING:
        from typing import Dict, List, Optional
        from blackboxprotobuf.lib.pytypes import Message, TypeDefDict, FieldDefDict
        from blackboxprotobuf.lib.config import Config


def decode_message(buf, message_type=None, config=None):
    # type: (bytes, Optional[str | TypeDefDict], Optional[Config]) -> tuple[Message, TypeDefDict]
    """解码 protobuf 消息并返回表示该消息的 Python 字典。

    Args:
        buf: 表示编码后的 protobuf 消息的字节数据
        message_type: 可选，用作解码基础的类型。允许自定义字段类型或名称。
            可以是 Python 字典，也可以是对应 config 中 `known_types` 字典的消息类型名称。
            默认为空定义 '{}'。
        config: `blackboxprotobuf.lib.config.Config` 对象，允许自定义
            线类型的默认类型，并包含 `known_types` 数组。
            如果未提供，默认为 `blackboxprotobuf.lib.config.default`。
    Returns:
        包含表示消息的 Python 字典和用于重新编码消息的类型定义的元组。

        类型定义基于提供的 `message_type` 参数（如果提供），
        但在解码过程中遇到新字段时可能会添加额外的字段。
    """

    if config is None:
        config = default_config

    if isinstance(buf, bytearray):
        buf = bytes(buf)
    buf = six.ensure_binary(buf)
    if message_type is None:
        message_type = {}
    elif isinstance(message_type, six.string_types):
        if message_type not in config.known_types:
            message_type = {}
        else:
            message_type = config.known_types[message_type]

    if not isinstance(message_type, dict):
        raise DecoderException(
            "Decode message received an invalid typedef type. Typedef should be a string with a message name, a dictionary, or None"
        )
    value, typedef, _, _ = blackboxprotobuf.lib.types.length_delim.decode_message(
        buf, config, TypeDef.from_dict(message_type)
    )
    return value, typedef.to_dict()


def encode_message(value, message_type, config=None):
    # type: (Message, str | TypeDefDict, Optional[Config]) -> bytes
    """将 Python 字典重新编码为二进制 protobuf 消息。

    Args:
        value: 要重新编码为字节的 Python 字典。通常是
            由 `decode_message` 返回的字典的修改版本。
        message_type: 用于重新编码消息的类型定义。
            通常是原始 `decode_message` 调用返回的类型定义。
        config: `blackboxprotobuf.lib.config.Config` 对象，允许自定义
            线类型的默认类型，并包含 `known_types` 数组。
            如果未提供，默认为 `blackboxprotobuf.lib.config.default`。
    Returns:
        包含编码后的 protobuf 消息的字节数组。
    """

    if config is None:
        config = default_config

    if message_type is None:
        raise EncoderException(
            "Encode message must have valid type definition. message_type cannot be None"
        )

    if isinstance(message_type, six.string_types):
        if message_type not in config.known_types:
            raise EncoderException(
                "The provided message type name (%s) is not known. Encoding requires a valid type definition"
                % message_type
            )
        message_type = config.known_types[message_type]

    if not isinstance(message_type, dict):
        raise EncoderException(
            "Encode message received an invalid typedef type. Typedef should be a string with a message name or a dictionary."
        )
    return bytes(
        blackboxprotobuf.lib.types.length_delim.encode_message(
            value, config, TypeDef.from_dict(message_type)
        )
    )


def protobuf_to_json(buf, message_type=None, config=None):
    # type: (bytes | list[bytes], Optional[str | TypeDefDict], Optional[Config]) -> tuple[str, TypeDefDict]
    """解码 protobuf 消息并返回表示消息的 JSON 字符串。

    Args:
        buf: 一个或多个表示编码后的 protobuf 消息的字节数据
        message_type: 可选，用作解码基础的类型。允许自定义字段类型或名称。
            可以是 Python 字典，也可以是对应 config 中 `known_types` 字典的消息类型名称。
            默认为空定义 '{}'。
        config: `blackboxprotobuf.lib.config.Config` 对象，允许自定义
            线类型的默认类型，并包含 `known_types` 数组。
            如果未提供，默认为 `blackboxprotobuf.lib.config.default`。
    Returns:
        包含表示消息的 JSON 字符串和用于重新编码消息的类型定义的元组。

        JSON 字符串和类型定义为了可读性而进行了注释和排序。

        类型定义基于提供的 `message_type` 参数（如果提供），
        但在解码过程中遇到新字段时可能会添加额外的字段。
    """
    values = []
    bufs = buf if isinstance(buf, list) else [buf]

    if len(bufs) == 0:
        raise DecoderException("No protobuf bytes were provided")

    for data in bufs:
        value, message_type = decode_message(data, message_type, config)
        value = _json_safe_transform(value, message_type, False, config=config)
        value = _sort_output(value, message_type, config=config)
        values.append(value)

    if not isinstance(message_type, dict):
        # 由于 len(bufs) 检查不应发生，但让类型检查器满意并验证边界情况
        raise DecoderException(
            "Error decoding to json: Could not find valid message_type type (dict). Found: %s"
            % type(message_type)
        )
    _annotate_typedef(message_type, values[0])
    message_type = sort_typedef(message_type)

    if not isinstance(buf, list) and len(values) == 1:
        return json.dumps(values[0], indent=2), message_type
    else:
        return json.dumps(values, indent=2), message_type


def protobuf_from_json(json_str, message_type, config=None):
    # type: (str, str | TypeDefDict, Optional[Config]) -> bytes | list[bytes]
    """将 JSON 字符串重新编码为二进制 protobuf 消息。

    Args:
        json_str: 要重新编码为 protobuf 消息字节的 JSON 字符串。
            通常是 `protobuf_to_json` 返回的值的修改版本。
        message_type: 用于重新编码消息的类型定义。
            通常是原始 `protobuf_to_json` 调用返回的类型定义。
        config: `blackboxprotobuf.lib.config.Config` 对象，允许自定义
            线类型的默认类型，并包含 `known_types` 数组。
            如果未提供，默认为 `blackboxprotobuf.lib.config.default`。
    Returns:
        包含编码后的 protobuf 消息的字节数组。
    """
    if config is None:
        config = default_config
    if isinstance(message_type, six.string_types):
        if message_type not in config.known_types:
            raise EncoderException(
                'protobuf_from_json must have valid type definition. message_type "%s" is not known'
                % message_type
            )
        message_type = config.known_types[message_type]
    if not isinstance(message_type, dict):
        raise EncoderException(
            "Encode message received an invalid typedef type. Typedef should be a string with a message name or a dictionary."
        )

    value = json.loads(json_str)
    values = value if isinstance(value, list) else [value]

    _strip_typedef_annotations(message_type)
    values = [_json_safe_transform(message, message_type, True) for message in values]

    payloads = []
    for message in values:
        payloads.append(encode_message(message, message_type, config))

    if not isinstance(value, list) and len(payloads) == 1:
        return payloads[0]
    else:
        return payloads


def export_protofile(message_types, output_filename):
    # type: (Dict[str, TypeDefDict], str) -> None
    """此函数尝试将一组消息类型定义导出为 `.proto` 文件，以便与其他工具一起使用。

    Args:
        message_types: 包含要导出的类型定义的 Python 字典。
            字典的键为消息类型名称，值为类型定义。
        output_filename: 表示输出 protobuf 定义文件的文件名字符串。
    """
    blackboxprotobuf.lib.protofile.export_proto(
        message_types, output_filename=output_filename
    )


def import_protofile(input_filename, save_to_known=True, config=None):
    # type: (str, bool, Optional[Config]) -> Dict[str, TypeDefDict] | None
    """此函数尝试从 `.proto` 文件导入一组消息类型定义。

    这是 `blackboxprotobuf.lib.protofile` 的便捷函数。
    protobuf 文件导入支持不完整，可能对某些类型定义失败。

    Args:
        input_filename: 要读取 protobuf 定义的文件名。
        save_to_known: 如果为 True，此函数将消息类型定义
            保存到 `config.known_types`。否则，将其返回给调用者。
            默认为 `True`。
        config: 可选配置对象，存储 `known_types` 映射。
            默认为 `blackboxprotobuf.lib.config.default`。
    Returns:
        如果 `save_to_known` 为 False，则从文件读取的类型定义
        以字典形式返回，键为类型名称，值为类型定义。
    """
    if config is None:
        config = default_config

    new_typedefs = blackboxprotobuf.lib.protofile.import_proto(
        config, input_filename=input_filename
    )
    if save_to_known:
        config.known_types.update(new_typedefs)
        return None
    else:
        return new_typedefs


NAME_REGEX = re.compile(r"\A[a-zA-Z][a-zA-Z0-9_]*\Z")


def validate_typedef(typedef, old_typedef=None, config=None, _path=None):
    # type: (TypeDefDict, Optional[TypeDefDict], Optional[Config], Optional[List[str]]) -> None
    """尝试验证类型定义对象是否有效。

    此函数尝试确保类型定义在用于编码/解码消息之前是有效的。
    它将确保字段名称有效且字段名称/编号一致。
    旨在在用户编辑类型定义后调用，以确保编辑有效。

    Args:
        typedef: 要验证的类型定义对象。应为从解码函数返回的
            Python 字典派生而来。
        old_typedef: 可选，提供旧版本的类型定义以与新类型定义进行比较。
            如果提供，此函数将确保任何类型更改是有效的。
            例如，varint 类型的字段可以更改为其他 varint 类型，
            但不能更改为字符串或浮点数。
        config: 可选，提供包含 `known_types` 映射的配置对象，
            用于将消息类型名称映射到已知的类型定义。
            默认为 `blackboxprotobuf.lib.config.default`。
    Raises:
        TypedefException: 如果提供的类型定义无效，则引发 TypedefException。
    """
    if _path is None:
        _path = []
    if config is None:
        config = default_config

    int_keys = set()
    field_names = set()
    for field_number, field_typedef in typedef.items():
        alt_field_number = None
        if "-" in str(field_number):
            field_number, alt_field_number = field_number.split("-")

        # 验证 field_number 是数字
        if not str(field_number).isdigit():
            raise TypedefException("Field number must be a digit: %s" % field_number)
        field_number = six.ensure_text(str(field_number))

        field_path = _path[:]
        field_path.append(field_number)

        # 检查重复的字段编号
        if field_number in int_keys:
            raise TypedefException(
                "Duplicate field number: %s" % field_number, field_path
            )
        int_keys.add(field_number)

        # 必须有 type 字段
        if "type" not in field_typedef:
            raise TypedefException(
                "Field number must have a type value: %s" % field_number, field_path
            )
        if alt_field_number is not None:
            if field_typedef["type"] != "message":
                raise TypedefException(
                    "Alt field number (%s) specified for non-message field: %s"
                    % (alt_field_number, field_number),
                    field_path,
                )

        valid_type_fields = [
            "type",
            "name",
            "field_order",
            "message_typedef",
            "message_type_name",
            "alt_typedefs",
            "example_value_ignored",
            "seen_repeated",
        ]
        for key, value in field_typedef.items():
            # 检查字段键是否为有效值
            if key not in valid_type_fields:
                raise TypedefException(
                    'Invalid field key "%s" for field number %s' % (key, field_number),
                    field_path,
                )
            if (
                key in ["message_typedef", "message_type_name"]
                and not field_typedef["type"] == "message"
            ):
                raise TypedefException(
                    'Invalid field key "%s" for field number %s' % (key, field_number),
                    field_path,
                )
            if key == "group_typedef" and not field_typedef["type"] == "group":
                raise TypedefException(
                    'Invalid field key "%s" for field number %s' % (key, field_number),
                    field_path,
                )

            # 验证 type 值
            if key == "type":
                if value not in blackboxprotobuf.lib.types.type_maps.WIRETYPES:
                    raise TypedefException(
                        'Invalid type "%s" for field number %s' % (value, field_number),
                        field_path,
                    )
            # 检查重复的名称
            if key == "name":
                if not isinstance(value, six.string_types):
                    raise TypedefException(
                        "Invalid type for name field in typedef: %r. Field number %s"
                        % (value, field_number),
                        field_path,
                    )
                if value.strip() == "":
                    continue

                if value.lower() in field_names:
                    raise TypedefException(
                        ('Duplicate field name "%s" for field ' "number %s")
                        % (value, field_number),
                        field_path,
                    )
                if not NAME_REGEX.match(value):
                    raise TypedefException(
                        (
                            'Invalid field name "%s" for field '
                            "number %s. Should match %s"
                        )
                        % (value, field_number, "[a-zA-Z_][a-zA-Z0-9_]*"),
                        field_path,
                    )
                field_names.add(value.lower())

            # 检查消息类型名称是否已知
            if key == "message_type_name":
                if value not in config.known_types:
                    raise TypedefException(
                        (
                            'Message type "%s" for field number'
                            " %s is not known. Known types: %s"
                        )
                        % (value, field_number, config.known_types.keys()),
                        field_path,
                    )

            # 递归验证内部 typedef
            if key == "message_typedef":
                if isinstance(value, dict):
                    if (
                        old_typedef is not None
                        and field_number in old_typedef
                        and key in old_typedef[field_number]
                    ):
                        validate_typedef(
                            value,
                            old_typedef=old_typedef[field_number]["message_typedef"],
                            _path=field_path,
                            config=config,
                        )
                    else:
                        validate_typedef(value, _path=field_path, config=config)
            if key == "alt_typedefs":
                for alt_field_number, alt_typedef in field_typedef[
                    "alt_typedefs"
                ].items():
                    if isinstance(alt_typedef, dict):
                        validate_typedef(alt_typedef, _path=field_path, config=config)

    if old_typedef is not None:
        wiretype_map = {}
        for field_number, value in old_typedef.items():
            wiretype_map[
                int(field_number)
            ] = blackboxprotobuf.lib.types.type_maps.WIRETYPES[value["type"]]
        for field_number, value in typedef.items():
            field_path = _path[:]
            field_path.append(str(field_number))
            if int(field_number) in wiretype_map:
                old_wiretype = wiretype_map[int(field_number)]
                if (
                    old_wiretype
                    != blackboxprotobuf.lib.types.type_maps.WIRETYPES[value["type"]]
                ):
                    raise TypedefException(
                        (
                            "Wiretype for field number %s does"
                            " not match old type definition"
                        )
                        % field_number,
                        field_path,
                    )


def _json_safe_transform(values, typedef, toBytes, config=None):
    # type: (Message, TypeDefDict, bool, Optional[Config]) -> Message
    # Python 的 JSON 没有默认方式处理 'bytes' 类型。为了处理这个问题，
    # 我们想要某种类似于字符串的编码，JSON 可以处理但也能处理任意字节。
    # 这种方法比仅仅转换所有字节更复杂，因为在重新编码时，
    # 我们需要知道哪些是转换过的，哪些原本就应该是字符串。

    # 像 hex 或 base64 这样为二进制设计的编码方式会更"合适"，
    # 但对于阅读者来说并不能提供任何信息。在某些情况下，
    # 二进制 blob 中可能包含内嵌的字符串或整数值，快速浏览会很有帮助。

    # 这里使用 latin1 编码，因为它可以处理任意字节，
    # 打印 ASCII 字符，并且可以解码回完全相同字节串。
    # 可能还有其他编码方式在 Python2.7 和 Python3.9 中都满足这些属性，
    # 但在处理其他反斜杠转义机制时，解析回字节时遇到了问题。

    if config is None:
        config = default_config
    name_map = {
        item["name"]: number
        for number, item in typedef.items()
        if ("name" in item and item["name"] != "")
    }
    if not isinstance(values, dict):
        # 此函数只应在消息上调用，如果不是则报错退出。
        # 这通常意味着类型被错误地交换了。
        raise EncoderException(
            "Error performing _json_safe_transform on message. Field was expected to be a message but was not: %r"
            % values
        )
    for name, value in values.items():
        if isinstance(name, int):
            name = six.ensure_text(str(name))
        alt_number = None
        base_name = name
        if "-" in name:
            base_name, alt_number = name.split("-")

        if base_name in name_map:
            field_number = name_map[base_name]
        else:
            field_number = base_name

        if field_number not in typedef or "type" not in typedef[field_number]:
            raise EncoderException(
                "Field %r not found in typedef or does not have type attribute."
                % field_number
            )

        field_type = typedef[field_number]["type"]  # type: str | TypeDefDict
        if field_type == "message":
            field_typedef = _get_typedef_for_message(typedef[field_number], config)
            if alt_number is not None:
                # 如果有替代类型，则查找它
                if alt_number not in typedef[field_number].get("alt_typedefs", {}):
                    raise TypedefException(
                        (
                            "Provided alt field name/number "
                            "%s is not valid for field_number %s"
                        )
                        % (alt_number, field_number)
                    )
                field_type = typedef[field_number]["alt_typedefs"][alt_number]
                if isinstance(field_type, dict):
                    field_typedef = field_type
                    field_type = "message"

        is_list = isinstance(value, list)
        field_values = value if is_list else [value]
        for i, field_value in enumerate(field_values):
            if field_type == "bytes":
                if toBytes:
                    field_values[i] = field_value.encode("latin1")
                else:
                    field_values[i] = field_value.decode("latin1")
            elif field_type == "message":
                field_values[i] = _json_safe_transform(
                    field_value,
                    field_typedef,
                    toBytes,
                    config=config,
                )

        # 如果需要，转换回单值
        if not is_list:
            values[name] = field_values[0]
        else:
            values[name] = field_values
    return values


def _get_typedef_for_message(field_typedef, config):
    # type: (FieldDefDict, Config) -> TypeDefDict
    assert field_typedef["type"] == "message"
    if "message_typedef" in field_typedef:
        return field_typedef["message_typedef"]
    elif field_typedef.get("message_type_name"):
        if field_typedef["message_type_name"] not in config.known_types:
            raise TypedefException(
                "Got 'message_type_name' not in known_messages: %s"
                % field_typedef["message_type_name"]
            )
        return config.known_types[field_typedef["message_type_name"]]
    else:
        raise TypedefException(
            "Got 'message' type without typedef or type name: %s" % field_typedef
        )


def _sort_output(value, typedef, config=None):
    # type: (Message, TypeDefDict, Optional[Config]) -> Message
    # 按 typedef 中的字段编号排序输出。有助于提高 JSON 转储的可读性。
    output_dict = collections.OrderedDict()  # type: Message
    if config is None:
        config = default_config

    # 创建所有字段名称的列表，同时聚合替代字段
    field_names = {}  # type: Dict[str, List[tuple[str, str | None]]]
    for field_name in value.keys():
        if isinstance(field_name, int):
            field_name = six.ensure_text(str(field_name))
        if "-" in field_name:
            field_name_base, alt_number = field_name.split("-")
        else:
            field_name_base = field_name
            alt_number = None
        field_names.setdefault(field_name_base, []).append((field_name, alt_number))

    for field_number, field_def in sorted(typedef.items(), key=lambda t: int(t[0])):
        field_number = six.ensure_text(str(field_number))
        seen_field_names = field_names.get(field_number, [])

        # 也尝试按名称获取匹配的字段
        if field_def.get("name", "") != "":
            field_name = field_def["name"]
            seen_field_names.extend(field_names.get(field_name, []))

        for field_name, alt_number in seen_field_names:
            field_type = field_def["type"]
            field_message_typedef = None
            if field_type == "message":
                field_message_typedef = _get_typedef_for_message(field_def, config)

            if alt_number is not None:
                if alt_number not in field_def["alt_typedefs"]:
                    raise TypedefException(
                        (
                            "Provided alt field name/number "
                            "%s is not valid for field_number %s"
                        )
                        % (alt_number, field_number)
                    )
                alt_field_type = field_def["alt_typedefs"][alt_number]
                if isinstance(alt_field_type, dict):
                    field_message_typedef = alt_field_type
                    field_type = "message"
                else:
                    field_type = alt_field_type

            if field_type == "message":
                if field_message_typedef is None:
                    raise TypedefException(
                        'Message does not have an associated typedef: "%s"' % field_name
                    )
                field_value = value.get(field_name)
                if isinstance(field_value, list):
                    output_dict[field_name] = []
                    for field_value_item in field_value:
                        if not isinstance(field_value_item, dict):
                            raise TypedefException(
                                'Message values must be a dictionary type. Field name: "%s"'
                                % field_name
                            )
                        output_dict[field_name].append(
                            _sort_output(field_value_item, field_message_typedef)
                        )
                else:
                    if not isinstance(field_value, dict):
                        raise TypedefException(
                            'Message values must be a dictionary type. Field name: "%s"'
                            % field_name
                        )
                    output_dict[field_name] = _sort_output(
                        field_value, field_message_typedef
                    )
            else:
                output_dict[field_name] = value[field_name]

    return output_dict


def sort_typedef(typedef):
    # type: (TypeDefDict) -> TypeDefDict
    """对类型定义应用特殊排序规则以提高可读性。

    对类型定义的字段进行排序，使得 'type' 或 'name' 等重要字段
    位于顶部，不会被 'message_typedef' 等较长字段埋没。
    同时也会根据字段编号对 'message_typedef' 的键进行排序。
    Args:
        typedef - 表示 Blackboxprotobuf 类型定义的字典
    Returns:
        一个新的 OrderedDict 对象，包含为可读性排序后的 typedef 参数内容。
    """

    # 按字段编号和子键排序，使 name 和 type 排在前面

    TYPEDEF_KEY_ORDER = [
        "name",
        "type",
        "message_type_name",
        "example_value_ignored",
        "field_order",
        "seen_repeated",
        "message_typedef",
        "alt_typedefs",
    ]
    output_dict = collections.OrderedDict()

    for field_number, field_def in sorted(
        typedef.items(), key=lambda t: int(t[0])
    ):  # 按类型编号排序
        output_field_def = collections.OrderedDict()
        for key, value in sorted(
            field_def.items(), key=lambda t: (TYPEDEF_KEY_ORDER.index(t[0]), t[1])
        ):  # 按特殊键排序，然后按值排序
            if key == "message_typedef":
                output_field_def[key] = sort_typedef(value)  # type: ignore
            else:
                output_field_def[key] = value  # type: ignore

        output_dict[field_number] = output_field_def
    if six.PY3 and typing.TYPE_CHECKING:
        return typing.cast(
            TypeDefDict, output_dict
        )  # Cast because typing doesn't like the ordered dict
    return output_dict


def _annotate_typedef(typedef, message):
    # type: (TypeDefDict, Message) -> None
    # 将消息中的值添加到 typedef 中，以便在手动编辑时更容易确定哪个字段对应什么值

    for field_number, field_def in typedef.items():
        field_value = None
        field_name = six.ensure_text(str(field_number))
        if field_name not in message and field_def.get("name", "") != "":
            field_name = field_def["name"]

        if field_name in message:
            field_value = message[field_name]

            if field_def["type"] == "message":
                if isinstance(field_value, list):
                    for value in field_value:
                        _annotate_typedef(field_def["message_typedef"], value)
                else:
                    _annotate_typedef(field_def["message_typedef"], field_value)
            else:
                field_def["example_value_ignored"] = field_value

        # 如果字段没有名称，添加一个空名称字段，以便更容易添加
        if "name" not in field_def:
            field_def["name"] = six.u("")


def _strip_typedef_annotations(typedef):
    # type: (TypeDefDict) -> None
    # 移除由 _annotate_typedef 添加的示例值
    for _, field_def in typedef.items():
        if "example_value_ignored" in field_def:
            del field_def["example_value_ignored"]
        if "message_typedef" in field_def:
            _strip_typedef_annotations(field_def["message_typedef"])
