"""包含 protobuf 类型的各种映射，包括编码/解码
函数、线缆类型（wiretype）和默认类型
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

from bbpb_cn.lib.types import varint, fixed, length_delim, wiretypes

import six

if six.PY3:
    from typing import Any, Callable, Dict, Tuple

# 将 bbpb_cn 类型映射到具体的编码器
ENCODERS = {
    "uint": varint.encode_uvarint,
    "int": varint.encode_varint,
    "sint": varint.encode_svarint,
    "fixed32": fixed.encode_fixed32,
    "sfixed32": fixed.encode_sfixed32,
    "float": fixed.encode_float,
    "fixed64": fixed.encode_fixed64,
    "sfixed64": fixed.encode_sfixed64,
    "double": fixed.encode_double,
    "bytes": length_delim.encode_bytes,
    "bytes_hex": length_delim.encode_bytes_hex,
    "string": length_delim.encode_string,
    "packed_uint": length_delim.generate_packed_encoder(varint.encode_uvarint),
    "packed_int": length_delim.generate_packed_encoder(varint.encode_varint),
    "packed_sint": length_delim.generate_packed_encoder(varint.encode_svarint),
    "packed_fixed32": length_delim.generate_packed_encoder(fixed.encode_fixed32),
    "packed_sfixed32": length_delim.generate_packed_encoder(fixed.encode_sfixed32),
    "packed_float": length_delim.generate_packed_encoder(fixed.encode_float),
    "packed_fixed64": length_delim.generate_packed_encoder(fixed.encode_fixed64),
    "packed_sfixed64": length_delim.generate_packed_encoder(fixed.encode_sfixed64),
    "packed_double": length_delim.generate_packed_encoder(fixed.encode_double),
}  # type: Dict[str, Callable[[Any], bytes]]

# 将 bbpb_cn 类型映射到具体的解码器
DECODERS = {
    "uint": varint.decode_uvarint,
    "int": varint.decode_varint,
    "sint": varint.decode_svarint,
    "fixed32": fixed.decode_fixed32,
    "sfixed32": fixed.decode_sfixed32,
    "float": fixed.decode_float,
    "fixed64": fixed.decode_fixed64,
    "sfixed64": fixed.decode_sfixed64,
    "double": fixed.decode_double,
    "bytes": length_delim.decode_bytes,
    "bytes_hex": length_delim.decode_bytes_hex,
    "string": length_delim.decode_string,
    "packed_uint": length_delim.generate_packed_decoder(varint.decode_uvarint),
    "packed_int": length_delim.generate_packed_decoder(varint.decode_varint),
    "packed_sint": length_delim.generate_packed_decoder(varint.decode_svarint),
    "packed_fixed32": length_delim.generate_packed_decoder(fixed.decode_fixed32),
    "packed_sfixed32": length_delim.generate_packed_decoder(fixed.decode_sfixed32),
    "packed_float": length_delim.generate_packed_decoder(fixed.decode_float),
    "packed_fixed64": length_delim.generate_packed_decoder(fixed.decode_fixed64),
    "packed_sfixed64": length_delim.generate_packed_decoder(fixed.decode_sfixed64),
    "packed_double": length_delim.generate_packed_decoder(fixed.decode_double),
}  # type: Dict[str, Callable[[bytes, int], Tuple[Any, int]  ]]

WIRETYPES = {
    "uint": wiretypes.VARINT,
    "int": wiretypes.VARINT,
    "sint": wiretypes.VARINT,
    "fixed32": wiretypes.FIXED32,
    "sfixed32": wiretypes.FIXED32,
    "float": wiretypes.FIXED32,
    "fixed64": wiretypes.FIXED64,
    "sfixed64": wiretypes.FIXED64,
    "double": wiretypes.FIXED64,
    "bytes": wiretypes.LENGTH_DELIMITED,
    "bytes_hex": wiretypes.LENGTH_DELIMITED,
    "string": wiretypes.LENGTH_DELIMITED,
    "message": wiretypes.LENGTH_DELIMITED,
    "group": wiretypes.START_GROUP,
    "packed_uint": wiretypes.LENGTH_DELIMITED,
    "packed_int": wiretypes.LENGTH_DELIMITED,
    "packed_sint": wiretypes.LENGTH_DELIMITED,
    "packed_fixed32": wiretypes.LENGTH_DELIMITED,
    "packed_sfixed32": wiretypes.LENGTH_DELIMITED,
    "packed_float": wiretypes.LENGTH_DELIMITED,
    "packed_fixed64": wiretypes.LENGTH_DELIMITED,
    "packed_sfixed64": wiretypes.LENGTH_DELIMITED,
    "packed_double": wiretypes.LENGTH_DELIMITED,
}  # type: Dict[str, int]

# 解码每个线缆类型时使用的默认值
# length delimited 是特殊的，在 length_delim 模块中处理
WIRE_TYPE_DEFAULTS = {
    wiretypes.VARINT: "int",
    wiretypes.FIXED32: "fixed32",
    wiretypes.FIXED64: "fixed64",
    wiretypes.LENGTH_DELIMITED: None,
    wiretypes.START_GROUP: None,
    wiretypes.END_GROUP: None,
}  # type: Dict[int, str | None]
