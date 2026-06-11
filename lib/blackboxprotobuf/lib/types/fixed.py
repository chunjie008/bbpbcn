"""对固定大小的整数和浮点数进行编码和解码的函数"""

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

import struct
import binascii
import six
from blackboxprotobuf.lib.exceptions import DecoderException, EncoderException

import six

if six.PY3:
    from typing import Any, Tuple


# 基于 "struct" 格式对结构体进行编码/解码的通用函数
def encode_struct(fmt, value):
    # type: (str, Any) -> bytes
    """编码任意Python "struct" 值的通用方法"""
    try:
        return struct.pack(fmt, value)
    except struct.error as exc:
        six.raise_from(
            EncoderException(
                "Error encoding value %r with format string %s" % (value, fmt)
            ),
            exc,
        )


def decode_struct(fmt, buf, pos):
    # type: (str, bytes, int) -> Tuple[Any, int]
    """解码任意Python "struct" 值的通用方法"""
    new_pos = pos + struct.calcsize(fmt)
    try:
        return struct.unpack(fmt, buf[pos:new_pos])[0], new_pos
    except struct.error as exc:
        six.raise_from(
            DecoderException(
                "Error deocding format string %s from bytes: %r"
                % (fmt, binascii.hexlify(buf[pos:new_pos]))
            ),
            exc,
        )


_fixed32_fmt = "<I"

# 类型说明：我们对解码后的对象使用 Any。虽然我们可以手动
# 强制单独的类型，但由于 `struct` 的原因，我们仍然需要
# 通过 `typing.cast` 来实现。Message 类型本身也有 `Any`。


def encode_fixed32(value):
    # type: (Any) -> bytes
    """编码单个32位固定大小值"""
    return encode_struct(_fixed32_fmt, value)


def decode_fixed32(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个32位固定大小值"""
    return decode_struct(_fixed32_fmt, buf, pos)


_sfixed32_fmt = "<i"


def encode_sfixed32(value):
    # type: (Any) -> bytes
    """编码单个有符号32位固定大小值"""
    return encode_struct(_sfixed32_fmt, value)


def decode_sfixed32(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个有符号32位固定大小值"""
    return decode_struct(_sfixed32_fmt, buf, pos)


_float_fmt = "<f"


def encode_float(value):
    # type: (Any) -> bytes
    """编码单个32位浮点数值"""
    return encode_struct(_float_fmt, value)


def decode_float(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个32位浮点数值"""
    return decode_struct(_float_fmt, buf, pos)


_fixed64_fmt = "<Q"


def encode_fixed64(value):
    # type: (Any) -> bytes
    """编码单个64位固定大小值"""
    return encode_struct(_fixed64_fmt, value)


def decode_fixed64(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个64位固定大小值"""
    return decode_struct(_fixed64_fmt, buf, pos)


_sfixed64_fmt = "<q"


def encode_sfixed64(value):
    # type: (Any) -> bytes
    """编码单个有符号64位固定大小值"""
    return encode_struct(_sfixed64_fmt, value)


def decode_sfixed64(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个有符号64位固定大小值"""
    return decode_struct(_sfixed64_fmt, buf, pos)


_double_fmt = "<d"


def encode_double(value):
    # type: (Any) -> bytes
    """编码单个64位浮点数值"""
    return encode_struct(_double_fmt, value)


def decode_double(buf, pos):
    # type: (bytes, int) -> Tuple[Any, int]
    """解码单个64位浮点数值"""
    return decode_struct(_double_fmt, buf, pos)
