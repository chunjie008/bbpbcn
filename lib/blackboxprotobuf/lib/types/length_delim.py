"""用于编码和解码长度分隔（length delimited）字段的模块"""

# Copyright (c) 2018-2024 NCC Group Plc
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import binascii
import copy
import sys
import six
import logging

import blackboxprotobuf.lib
from blackboxprotobuf.lib.types import varint, wiretypes
from blackboxprotobuf.lib.exceptions import (
    EncoderException,
    DecoderException,
    TypedefException,
    BlackboxProtobufException,
)
from blackboxprotobuf.lib.typedef import (
    TypeDef,
    MutableTypeDef,
    FieldDef,
    MutableFieldDef,
)

if six.PY3:
    import typing

    if typing.TYPE_CHECKING:
        from blackboxprotobuf.lib.config import Config
        from typing import Any, Callable, Dict, Tuple, Optional, List
        from blackboxprotobuf.lib.pytypes import Message

logger = logging.getLogger(__name__)


def encode_string(value):
    # type: (Any) -> bytes
    """将字符串编码为长度分隔的字节数组"""
    try:
        value = six.ensure_text(value)
    except TypeError as exc:
        six.raise_from(
            EncoderException("Error encoding string to message: %r" % value), exc
        )
    return encode_bytes(value)


def encode_bytes(value):
    # type: (Any) -> bytes
    """编码一个长度分隔的字节数组"""
    if isinstance(value, bytearray):
        value = bytes(value)
    try:
        value = six.ensure_binary(value)
    except TypeError as exc:
        six.raise_from(
            EncoderException("Error encoding bytes to message: %r" % value), exc
        )

    if not isinstance(value, bytes):
        raise EncoderException(
            "encode_bytes must receive a bytes or bytearray value: %s %r"
            % (type(value), value)
        )
    encoded_length = varint.encode_varint(len(value))
    return encoded_length + value


def decode_bytes(buf, pos):
    # type: (bytes, int) -> Tuple[bytes, int]
    """从 buf 中解码一个长度分隔的字节数组"""
    length, pos = varint.decode_varint(buf, pos)
    end = pos + length
    try:
        return buf[pos:end], end
    except IndexError as exc:
        six.raise_from(
            DecoderException(
                (
                    "Error decoding bytes. Decoded length %d is longer than bytes"
                    " available %d"
                )
                % (length, len(buf) - pos)
            ),
            exc,
        )


def encode_bytes_hex(value):
    # type: (Any) -> bytes
    """编码一个由十六进制字符串表示的长度分隔字节数组"""
    try:
        return encode_bytes(binascii.unhexlify(value))
    except (TypeError, binascii.Error) as exc:
        six.raise_from(
            EncoderException("Error encoding hex bytestring %s" % value), exc
        )


def decode_bytes_hex(buf, pos):
    # type: (bytes, int) -> Tuple[bytes, int]
    """从 buf 中解码一个长度分隔的字节数组，并返回十六进制编码的字符串"""
    value, pos = decode_bytes(buf, pos)
    return binascii.hexlify(value), pos


def decode_string(value, pos):
    # type: (bytes, int) -> Tuple[str, int]
    """将长度分隔的字节数组解码为字符串"""
    length, pos = varint.decode_varint(value, pos)
    end = pos + length
    try:
        # 反斜杠转义不可逆
        return value[pos:end].decode("utf-8"), end
    except (TypeError, UnicodeDecodeError) as exc:
        six.raise_from(
            DecoderException("Error decoding UTF-8 string %r" % value[pos:end]), exc
        )


def encode_tag(field_number, wire_type):
    # type: (int, int) -> bytes
    # 此处不检查边界，应在之前检查
    tag_number = (field_number << 3) | wire_type
    return varint.encode_uvarint(tag_number)


def decode_tag(buf, pos):
    # type: (bytes, int) -> Tuple[int, int, int]
    tag_number, pos = varint.decode_uvarint(buf, pos)
    field_number = tag_number >> 3
    wire_type = tag_number & 0x7
    return field_number, wire_type, pos


def encode_message(data, config, typedef, path=None, field_order=None):
    # type: (Message, Config, TypeDef, Optional[List[str]], Optional[List[str]]) -> bytes
    """将 Python 字典编码为二进制 protobuf 消息"""
    output = bytearray()
    if path is None:
        path = []

    output_len = 0
    field_outputs = {}  # type: Dict[str, List[bytes]]
    for field_id, value in data.items():
        field_number, outputs = _encode_message_field(
            config, typedef, path, field_id, value
        )

        # 如果字段编号在数据中表示为多个位置
        # （例如，作为 int、作为名称、作为带有 int 的字符串）
        field_outputs.setdefault(field_number, []).extend(outputs)
        output_len += len(outputs)

    if output_len > 0:
        if (
            config.preserve_field_order
            and field_order is not None
            and len(field_order) == output_len
        ):
            # 检查旧的 typedef（其中 field_order 是元组）
            if isinstance(field_order[0], tuple):
                field_order = [x[0] for x in field_order]
            for field_number in field_order:
                try:
                    output += field_outputs[field_number].pop(0)
                except (IndexError, KeyError):
                    # 如果在我们检查了总长度后仍然不匹配，
                    # 那么可能字段命名有些异常。
                    # 这可能意味着顺序与原始顺序不一致，
                    # 但应该不会破坏真正的 protobuf 消息
                    logger.warning(
                        "The field_order list does not match the fields from _encode_message_field"
                    )
                    # 如果遇到字段顺序与实际数据不匹配，
                    # 则直接退出。剩下的可以正常编码
                    break

        # 将数组中的元素分组
        for values in field_outputs.values():
            for value in values:
                output += value

    return output


def _encode_message_field(config, typedef, path, field_id, value):
    # type: (Config, TypeDef, List[str], str | int, Any) -> Tuple[str, List[bytes]]

    if not isinstance(field_id, six.text_type):
        field_key = six.ensure_text(str(field_id))  # type: str
    else:
        field_key = field_id

    fielddef_results = typedef.lookup_fielddef(field_key)

    if fielddef_results is None:
        raise EncoderException(
            "Provided field name/number %s is not valid" % (field_key),
            path,
        )
    field_number, fielddef = fielddef_results

    field_path = path[:]
    field_path.append(str(field_number))

    field_type = fielddef.lookup_field_type(field_key, config, field_path)

    if field_type is None:
        raise EncoderException(
            "Provided field name/number %s / %s is not valid"
            % (field_key, field_number),
            field_path,
        )

    field_encoder = None  # type: Callable[[Any], bytes] | None
    if isinstance(field_type, TypeDef):
        field_typedef = field_type
        field_type = "message"
        field_encoder = lambda data: encode_lendelim_message(
            data,
            config,
            field_typedef,
            path=field_path,
            field_order=fielddef.field_order,
        )
    else:
        if field_type not in blackboxprotobuf.lib.types.ENCODERS:
            raise TypedefException("Unknown type: %s" % field_type)
        field_encoder = blackboxprotobuf.lib.types.ENCODERS[field_type]
        if field_encoder is None:
            raise TypedefException(
                "Encoder not implemented for %s" % field_type, field_path
            )

    # 编码标签（tag）
    tag = encode_tag(
        int(field_number), blackboxprotobuf.lib.types.WIRETYPES[field_type]
    )

    outputs = []
    try:
        # 重复值将分别编码并添加到 outputs 列表中
        # 打包值接收一个列表，但将它们编码为单个长度
        # 分隔字段，因此我们将它们作为非重复值处理
        if isinstance(value, list) and not field_type.startswith("packed_"):
            for repeated in value:
                outputs.append(tag + field_encoder(repeated))
        else:
            outputs.append(tag + field_encoder(value))

    except EncoderException as exc:
        exc.set_path(field_path)
        six.reraise(*sys.exc_info())

    return field_number, outputs


def decode_message(buf, config, typedef=None, pos=0, end=None, depth=0, path=None):
    # type: (bytes, Config, Optional[TypeDef], int, Optional[int], int, Optional[List[str]]) -> Tuple[Message, TypeDef, List[str], int]
    """解码不带长度前缀的 protobuf 消息"""
    if end is None:
        end = len(buf)

    if typedef is None:
        typedef = TypeDef()

    if path is None:
        path = []

    output = {}  # type: Message
    seen_repeated = {}  # type: Dict[str, bool]
    mut_typedef = typedef.make_mutable()

    grouped_fields, field_order, pos = _group_by_number(buf, pos, end, path)
    for field_number, (wire_type, buffers) in grouped_fields.items():
        # wire_type 应由 _group_by_number 验证

        field_path = path[:] + [field_number]

        fielddef_pair = mut_typedef.lookup_fielddef_number(
            field_number
        )  # type: Optional[Tuple[str, FieldDef]]

        if fielddef_pair is None:
            fielddef = FieldDef(field_number)
        else:
            fielddef = fielddef_pair[1]

        # 解码消息（可能有多个 typedef）或未知的长度分隔字段
        if wire_type == wiretypes.LENGTH_DELIMITED and not isinstance(
            fielddef.lookup_field_type_number("0", config, field_path), six.string_types
        ):
            output_map, new_fielddef = _try_decode_lendelim_fields(
                buffers, fielddef, config, field_path
            )

            # 将长度分隔字段合并到输出映射中
            for field_key, field_outputs in output_map.items():
                output.setdefault(field_key, []).extend(field_outputs)
            seen_repeated[fielddef.name] = new_fielddef.seen_repeated
            mut_typedef.set_fielddef(field_number, new_fielddef)
        else:
            field_outputs, new_fielddef, field_alt_type_id = _decode_standard_field(
                wire_type, buffers, fielddef, config, path
            )

            field_key = new_fielddef.field_key(field_alt_type_id)
            output.setdefault(field_key, []).extend(field_outputs)
            seen_repeated[fielddef.name] = new_fielddef.seen_repeated

            # 将字段 typedef/type 存回 typedef
            mut_typedef.set_fielddef(field_number, new_fielddef)

    _simplify_output(output, seen_repeated)
    return output, mut_typedef, field_order, pos


def _decode_standard_field(wire_type, buffers, fielddef, config, field_path):
    # type: (int, List[bytes], FieldDef, Config, List[str]) -> Tuple[List[Any], FieldDef, str]
    field_outputs = None
    field_alt_type_id = None
    for alt_type_id, field_type in fielddef.resolve_types(config, field_path).items():
        if isinstance(field_type, TypeDef):
            # 跳过消息类型
            continue
        if (
            not isinstance(field_type, six.string_types)
            or blackboxprotobuf.lib.types.WIRETYPES[field_type] != wire_type
        ):
            raise DecoderException(
                "Type %s from typedef did not match wiretype %s"
                % (field_type, wire_type),
                path=field_path,
            )

        if field_type not in blackboxprotobuf.lib.types.DECODERS:
            raise TypedefException(
                "Type %s does not have a decoder" % (field_type),
                path=field_path,
            )
        decoder = blackboxprotobuf.lib.types.DECODERS[field_type]
        try:
            field_outputs = [decoder(buf, 0)[0] for buf in buffers]
            field_alt_type_id = alt_type_id
        except BlackboxProtobufException as exc:
            # 解码出错，尝试下一个（如果有）
            continue
        # 解码成功
        break

    if field_outputs is None:
        field_type = config.get_default_type(wire_type)
        default_decoder = blackboxprotobuf.lib.types.DECODERS[field_type]

        field_outputs = [default_decoder(buf, 0)[0] for buf in buffers]

    mut_fielddef = fielddef.make_mutable()
    if field_alt_type_id is None:
        field_alt_type_id = mut_fielddef.next_alt_type_id()

    mut_fielddef.set_type(field_alt_type_id, field_type)

    if field_outputs is None:
        raise DecoderException(
            "Unable to decode wire_type %s" % (wire_type),
            path=field_path,
        )
    if isinstance(field_type, six.string_types) and field_type.startswith("packed_"):
        # 打包解码将返回列表的列表
        field_outputs = [y for x in field_outputs for y in x]
        mut_fielddef.mark_repeated()
    # 如果有多个则标记为重复
    # 如果已经标记为重复则无需担心
    elif len(field_outputs) > 1:
        mut_fielddef.mark_repeated()

    return field_outputs, mut_fielddef, field_alt_type_id


def _simplify_output(output, seen_repeated):
    # type: (Message, Dict[str, bool]) -> None
    # 如果任何输出只有一个元素，则从列表转换为单个值
    # 会修改 output
    for field_key, field_outputs in output.items():
        if isinstance(field_outputs, list) and len(field_outputs) == 1:
            field_name = (
                field_key.split(six.u("-"), 1)[0]
                if isinstance(field_key, six.string_types)
                else six.ensure_text(str(field_key))
            )
            if not seen_repeated[field_name]:
                output[field_key] = field_outputs[0]


def _group_by_number(buf, pos, end, path):
    # type: (bytes, int, int, List[str]) -> Tuple[Dict[str, Tuple[int, List[bytes]]], List[str], int]
    # 解析整个消息，根据线缆类型（wire type）分割成缓冲区，
    # 并按字段编号组织。这迫使我们一次性解析整个
    # 消息，但我觉得我们已经这样做了。这也可以及早捕获大小
    # 错误，这通常是指示是否为
    # protobuf 消息的最佳指标。
    # 返回一个字典，格式如下：
    #     {
    #         "2": (<wiretype>, [<data>])
    #     }

    output_map = {}  # type: Dict[str, Tuple[int, List[bytes]]]
    field_order = []
    while pos < end:
        # 读取一个字段
        field_number, wire_type, pos = decode_tag(buf, pos)

        # 我们希望字段编号在所有地方都作为字符串
        field_id = six.ensure_text(str(field_number))

        field_path = path[:] + [field_id]

        if field_id in output_map and output_map[field_id][0] != wire_type:
            # 这种情况不应该发生
            raise DecoderException(
                "Field %s has mistmatched wiretypes. Previous: %s Now: %s"
                % (field_id, output_map[field_id][0], wire_type),
                path=field_path,
            )

        length = None
        if wire_type == wiretypes.VARINT:
            # 实际上需要读取整个 varint 才能确定其大小
            _, new_pos = varint.decode_uvarint(buf, pos)
            length = new_pos - pos
        elif wire_type == wiretypes.FIXED32:
            length = 4
        elif wire_type == wiretypes.FIXED64:
            length = 8
        elif wire_type == wiretypes.LENGTH_DELIMITED:
            # 从消息开头读取长度
            # 同时加上长度标签本身的长度
            bytes_length, new_pos = varint.decode_varint(buf, pos)
            length = bytes_length + (new_pos - pos)
        elif wire_type in [
            wiretypes.START_GROUP,
            wiretypes.END_GROUP,
        ]:
            raise DecoderException("GROUP wire types not supported", path=field_path)
        else:
            raise DecoderException(
                "Got unknown wire type: %d" % wire_type, path=field_path
            )
        if pos + length > end:
            raise DecoderException(
                "Decoded length for field %s goes over end: %d > %d"
                % (field_id, pos + length, end),
                path=field_path,
            )

        field_buf = buf[pos : pos + length]

        if field_id in output_map:
            output_map[field_id][1].append(field_buf)
        else:
            output_map[field_id] = (wire_type, [field_buf])
        field_order.append(field_id)
        pos += length
    return output_map, field_order, pos


def _try_decode_lendelim_fields(buffers, fielddef, config, path):
    # type: (List[bytes], FieldDef, Config, List[str]) -> Tuple[Message, FieldDef]
    # 会修改 message_output

    # 这里开始变得复杂
    # 首先，由于我们希望解码消息而不是将每个
    # 嵌入式消息视为字节，我们必须猜测它是否是消息。
    # 与其他类型不同，我们不能假设消息类型在
    # 整个树中甚至在同一消息内是一致的。
    # 一个字段可能是 bytes 类型，解码为多个不同的
    # 消息，而这些消息没有相同的类型定义。这就是
    # 'alt_typedefs' 让我们能够指定该字段
    # 所见过的不同消息类型。
    # 一般来说，如果某个东西曾成功解码为消息，其余也应该可以，
    # 我们可以在单条消息内强制执行这一点，但不能跨多条
    # 消息。
    # 这将稍微改变 "alt_typedefs" 的定义，从仅仅
    # 替代消息类型定义，到也允许降级为
    # 'bytes' 或带有 'alt_type' 的字符串（如果解析失败）

    message_output = {}  # type: Message

    # TODO 潜在性能改进：使用 {} 进行第一遍扫描，或按编号分组，使用结果验证是否为有效的 protobuf 并快速将 wire_types 与 typedefs 匹配
    try:
        outputs_map = {}  # type: Dict[str, Any]
        field_order = []  # type: List[str]

        next_alt_type_id = int(fielddef.next_alt_type_id())
        field_types = fielddef.resolve_types(config, path)

        # 我们不希望在这个循环内发生任何可变更改，我们希望
        # 如果失败，所有内容都能回滚
        for buf in buffers:
            output = None
            output_typedef = None
            output_typedef_num = None
            new_field_order = []  # type: List[str]

            for alt_type_id, field_type in sorted(
                field_types.items(), key=lambda x: int(x[0])
            ):
                # 跳过非消息类型
                if not isinstance(field_type, TypeDef):
                    continue

                try:
                    (
                        output,
                        output_typedef,
                        new_field_order,
                        _,
                    ) = decode_lendelim_message(buf, config, field_type)
                except Exception as exc:
                    # 如果出现异常，则说明这不是正确的 typedef，尝试下一个
                    continue

                output_typedef_num = alt_type_id
                # 如果没有异常，则找到了正确的类型
                break
            # 如果上面没有找到类型，则尝试匿名类型
            # 如果这仍然失败，则对所有类型回退到 string 和 bytes
            if output is None:
                output, output_typedef, new_field_order, _ = decode_lendelim_message(
                    buf, config, None
                )
                output_typedef_num = six.ensure_text(str(next_alt_type_id))
                next_alt_type_id += 1

            if output_typedef is None or output_typedef_num is None:
                raise DecoderException(
                    "Could not find an output_typedef or output_typedef_num. This should not happen under any circumstances."
                )

            # 保存找到的 output 或 typedef
            field_types[output_typedef_num] = output_typedef
            outputs_map.setdefault(output_typedef_num, []).append(output)

            # 理论上，每个数据实例应有不同的字段顺序
            # 但这需要非常混乱的 JSON，这是我们试图避免的
            if len(new_field_order) > len(field_order):
                field_order = new_field_order

        # 成功将所有内容解码为消息
        mut_fielddef = fielddef.make_mutable()
        mut_fielddef.set_types(field_types)

        if config.preserve_field_order:
            mut_fielddef.set_field_order(field_order)

        # 消息被设置为 "key-alt_number"
        for output_typedef_num, outputs in outputs_map.items():
            output_field_key = mut_fielddef.field_key(output_typedef_num)

            message_output[output_field_key] = outputs
            if len(outputs) > 1:
                mut_fielddef.mark_repeated()

        # 成功，返回
        return message_output, mut_fielddef
    except DecoderException as exc:
        # 这种情况应该很常见，不要发出噪音或抛出异常
        logger.debug(
            "Could not decode a buffer for field (%s) as a message: %s",
            path,
            exc,
        )

    # 作为消息解码失败，尝试字符串，然后是配置的二进制类型
    # 默认情况下，default_binary_type 将与 bytes 冗余，但我们希望
    # 如果 default_binary_type 因任何原因失败，回退到 bytes
    for target_type in ["string", config.default_binary_type, "bytes"]:
        try:
            outputs = []
            decoder = blackboxprotobuf.lib.types.DECODERS[target_type]
            for buf in buffers:
                output, _ = decoder(buf, 0)
                outputs.append(output)

            field_alt_type_id = None
            # 检查类型是否已知
            field_types = fielddef.resolve_types(config, path)
            for alt_type_id, field_type in field_types.items():
                if field_type == target_type:
                    field_alt_type_id = alt_type_id
                    break

            mut_fielddef = fielddef.make_mutable()
            if field_alt_type_id is None:
                field_alt_type_id = mut_fielddef.add_type(target_type)

            field_key = mut_fielddef.field_key(field_alt_type_id)  # type: str

            message_output[field_key] = outputs
            return message_output, mut_fielddef
        except DecoderException:
            continue

    # 这不应该发生，我们应该总是能够使用 bytes
    raise DecoderException("Unable to decode field with typedef", path=path)


def encode_lendelim_message(data, config, typedef, path=None, field_order=None):
    # type: (Message, Config, TypeDef, Optional[List[str]], Optional[List[str]]) -> bytes
    """将数据编码为长度分隔的 protobuf 消息"""
    message_out = encode_message(
        data, config, typedef, path=path, field_order=field_order
    )
    length = varint.encode_varint(len(message_out))
    return length + message_out


def decode_lendelim_message(buf, config, typedef=None, pos=0, depth=0, path=None):
    # type: (bytes, Config, Optional[TypeDef], int, int, Optional[List[str]]) -> Tuple[Message, TypeDef, List[str], int]
    """从 buf 解码一条长度分隔的 protobuf 消息"""
    length, pos = varint.decode_varint(buf, pos)
    ret = decode_message(
        buf, config, typedef, pos, pos + length, depth=depth, path=path
    )
    return ret


def generate_packed_encoder(wrapped_encoder):
    # type: (Callable[[Any], bytes]) -> Callable[[List[Any]], bytes]
    """基于基础类型编码器生成打包类型的编码器"""

    def length_wrapper(values):
        # type: (List[Any]) -> bytes
        # 编码重复值并在前面加上长度前缀
        output = bytearray()
        for value in values:
            output += wrapped_encoder(value)
        length = varint.encode_varint(len(output))
        return length + output

    return length_wrapper


def generate_packed_decoder(wrapped_decoder):
    # type: (Callable[[bytes, int], Tuple[Any, int]]) -> Callable[[bytes, int], Tuple[List[Any], int]]
    """基于基础类型解码器生成打包类型的解码器"""

    def length_wrapper(buf, pos):
        # type: (bytes, int) -> Tuple[List[Any], int]
        # 解码以长度前缀开头的重复值
        length, pos = varint.decode_varint(buf, pos)
        end = pos + length
        output = []
        while pos < end:
            value, pos = wrapped_decoder(buf, pos)
            output.append(value)
        if pos > end:
            raise DecoderException(
                (
                    "Error decoding packed field. Packed length larger than"
                    " buffer: decoded = %d, left = %d"
                )
                % (length, len(buf) - pos)
            )
        return output, pos

    return length_wrapper
