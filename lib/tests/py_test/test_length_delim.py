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

from hypothesis import given, assume, note, example, reproduce_failure
import hypothesis.strategies as st
import collections
import strategies
import six
import copy
import binascii

from blackboxprotobuf.lib.config import Config
from blackboxprotobuf.lib.types import length_delim
from blackboxprotobuf.lib.types import type_maps
from blackboxprotobuf.lib.typedef import TypeDef, FieldDef

if six.PY2:
    string_types = (unicode, str)
else:
    string_types = str


# 逆运算检查。确保 bbp 编码的值解码后得到相同的值
@given(x=strategies.input_map["bytes"])
def test_bytes_inverse(x):
    encoded = length_delim.encode_bytes(x)
    decoded, pos = length_delim.decode_bytes(encoded, 0)
    assert isinstance(encoded, bytearray)
    assert isinstance(decoded, bytearray)
    assert pos == len(encoded)
    assert decoded == x


# 逆运算检查。确保 bbp 编码的值解码后得到相同的值
@given(x=strategies.input_map["bytes"])
def test_bytes_guess_inverse(x):
    config = Config()
    # 将消息包装在一个新消息中，以便内部进行类型猜测
    wrapper_typedef = {"1": {"type": "bytes"}}
    wrapper_message = {"1": x}

    encoded = length_delim.encode_lendelim_message(
        wrapper_message, config, TypeDef.from_dict(wrapper_typedef)
    )
    value, typedef, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef()
    )
    typedef = typedef.to_dict()

    # 如果猜测错误时希望测试失败，但有时可能会解析为消息
    assume(typedef["1"]["type"] == "bytes")

    assert isinstance(encoded, bytearray)
    assert isinstance(value["1"], bytearray)
    assert pos == len(encoded)
    assert value["1"] == x


@given(x=strategies.input_map["bytes"].map(binascii.hexlify))
def test_bytes_hex_inverse(x):
    encoded = length_delim.encode_bytes_hex(x)
    decoded, pos = length_delim.decode_bytes_hex(encoded, 0)
    assert isinstance(encoded, bytearray)
    assert isinstance(decoded, (bytearray, bytes))
    assert pos == len(encoded)
    assert decoded == x


@given(x=strategies.input_map["string"])
def test_string_inverse(x):
    encoded = length_delim.encode_bytes(x)
    decoded, pos = length_delim.decode_string(encoded, 0)
    assert isinstance(encoded, bytearray)
    assert isinstance(decoded, string_types)
    assert pos == len(encoded)
    assert decoded == x


@given(x=strategies.gen_message())
def test_message_inverse(x):
    config = Config()
    typedef, message = x
    encoded = length_delim.encode_lendelim_message(
        message, config, TypeDef.from_dict(typedef)
    )
    decoded, typedef_out, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef.from_dict(typedef), 0
    )
    typedef_out = typedef_out.to_dict()
    note(encoded)
    note(typedef)
    note(typedef_out)
    assert isinstance(encoded, bytearray)
    assert isinstance(decoded, dict)
    assert pos == len(encoded)
    assert message == decoded


@given(x=strategies.gen_message(anon=True))
def test_anon_decode(x):
    config = Config()
    typedef, message = x
    encoded = length_delim.encode_lendelim_message(
        message, config, TypeDef.from_dict(typedef)
    )
    decoded, typedef_out, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef(), 0
    )
    typedef_out = typedef_out.to_dict()
    note("原始消息: %r" % message)
    note("解码消息: %r" % decoded)
    note("原始 typedef: %r" % typedef)
    note("解码 typedef: %r" % typedef_out)

    def check_message(orig, orig_typedef, new, new_typedef):
        for field_number in set(orig.keys()) | set(new.keys()):
            # 跳过意外得到替代 typedef 的情况
            assume("-" not in field_number)
            # 验证所有字段都存在
            assert field_number in orig
            assert field_number in orig_typedef
            assert field_number in new
            assert field_number in new_typedef

            orig_values = orig[field_number]
            new_values = new[field_number]
            orig_type = orig_typedef[field_number]["type"]
            new_type = new_typedef[field_number]["type"]

            note("解析字段# %s" % field_number)
            note("原始值: %r" % orig_values)
            note("新值: %r" % new_values)
            note("原始类型: %s" % orig_type)
            note("新类型: %s" % new_type)
            # 字段可能是列表。将所有内容转换为列表
            if not isinstance(orig_values, list):
                orig_values = [orig_values]
                assert not isinstance(new_values, list)
                new_values = [new_values]

            # 如果类型不匹配，尝试转换
            if new_type == "message" and orig_type in ["bytes", "string"]:
                # 如果类型是消息，我们希望将原始类型转换为消息
                # 这并不理想，我们将使用非预期的类型，但
                # 这是比较的最佳方式。将消息重新编码为二进制可能
                # 不会保持字段顺序
                new_field_typedef = new_typedef[field_number]["message_typedef"]
                for i, orig_value in enumerate(orig_values):
                    if orig_type == "bytes":
                        (
                            orig_values[i],
                            orig_field_typedef,
                            _,
                            _,
                        ) = length_delim.decode_lendelim_message(
                            length_delim.encode_bytes(orig_value),
                            config,
                            TypeDef.from_dict(new_field_typedef),
                        )
                        orig_field_typedef = orig_field_typedef.to_dict()
                    else:
                        # 字符串值
                        (
                            orig_values[i],
                            orig_field_typedef,
                            _,
                            _,
                        ) = length_delim.decode_lendelim_message(
                            length_delim.encode_string(orig_value),
                            config,
                            TypeDef.from_dict(new_field_typedef),
                        )
                        orig_field_typedef = orig_field_typedef.to_dict()
                    orig_typedef[field_number]["message_typedef"] = orig_field_typedef
                orig_type = "message"

            if new_type == "string" and orig_type == "bytes":
                # 我们的字节被意外地解释成了有效字符串
                new_type = "bytes"
                for i, new_value in enumerate(new_values):
                    new_values[i], _ = length_delim.decode_bytes(
                        length_delim.encode_string(new_value), 0
                    )
            # 对列表进行排序，对字典特殊处理
            orig_values.sort(key=lambda x: x if not isinstance(x, dict) else x.items())
            new_values.sort(key=lambda x: x if not isinstance(x, dict) else x.items())
            for orig_value, new_value in zip(orig_values, new_values):
                if orig_type == "message":
                    check_message(
                        orig_value,
                        orig_typedef[field_number]["message_typedef"],
                        new_value,
                        new_typedef[field_number]["message_typedef"],
                    )
                else:
                    assert orig_value == new_value

    check_message(message, typedef, decoded, typedef_out)


@given(x=strategies.gen_message())
@example(x=({"1": {"seen_repeated": True, "type": "string"}}, {"1": ["", "0"]}))
@example(
    x=(
        {
            "1": {"seen_repeated": False, "type": "sfixed32"},
            "2": {"seen_repeated": True, "type": "string"},
        },
        {"1": 0, "2": ["0", "00"]},
    )
)
def test_message_guess_inverse(x):
    config = Config()
    type_def, message = x
    # 将消息包装在一个新消息中，以便内部进行类型猜测
    wrapper_typedef = {"1": {"type": "message", "message_typedef": type_def}}
    wrapper_message = {"1": message}

    encoded = length_delim.encode_lendelim_message(
        wrapper_message, config, TypeDef.from_dict(wrapper_typedef)
    )
    note("编码长度 %d" % len(encoded))
    value, decoded_type, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef()
    )
    decoded_type = decoded_type.to_dict()

    note(value)
    assert decoded_type["1"]["type"] == "message"

    assert isinstance(encoded, bytearray)
    assert isinstance(value, dict)
    assert isinstance(value["1"], dict)
    assert pos == len(encoded)


@given(bytes_in=st.binary())
def test_message_guess_bytes(bytes_in):
    # 测试给定的字节数组可以在不提供类型的情况下解码，然后重新编码为相同的字节

    config = Config()

    # 将其嵌入到另一个消息中，以便进行正确的类型猜测
    wrapper_typedef = {"1": {"type": "bytes"}}
    wrapper_message = {"1": bytes_in}
    bytes_in = length_delim.encode_message(
        wrapper_message, config, TypeDef.from_dict(wrapper_typedef)
    )

    decoded_message, guessed_typedef, field_order, pos = length_delim.decode_message(
        bytes_in, config, TypeDef()
    )
    guessed_typedef = guessed_typedef.to_dict()
    assert pos == len(bytes_in)
    bytes_out = length_delim.encode_message(
        decoded_message, config, TypeDef.from_dict(guessed_typedef)
    )
    assert bytes_in == bytes_out


@given(x=strategies.gen_message(anon=True), rng=st.randoms())
def test_message_ordering(x, rng):
    # 消息在编码然后解码时需要保持字段顺序
    # 理论上 protobuf 消息中字段顺序不应重要，但如果
    # 将一个非 protobuf 消息解码为 protobuf 然后再重新编码为
    # 字节，将会打乱字节顺序并违反"解码然后
    # 重新编码不应改变消息"的规则
    config = Config()
    typedef, message = x

    # 将消息包装在一个新消息中，以便内部进行类型猜测
    typedef = {"1": {"type": "message", "message_typedef": typedef}}
    message = {"1": message}

    # 先编码为字节
    message_bytes = length_delim.encode_message(
        message, config, TypeDef.from_dict(typedef)
    )

    # 现在我们有可以解码为消息的字节，我们不关心原始 typedef 是什么
    decoded_message, typedef, _, _ = length_delim.decode_message(
        message_bytes, config, TypeDef()
    )
    typedef = typedef.to_dict()

    message_items = list(decoded_message["1"].items())
    rng.shuffle(message_items)
    decoded_message["1"] = collections.OrderedDict(message_items)

    new_message_bytes = length_delim.encode_message(
        decoded_message, config, TypeDef.from_dict(typedef)
    )

    assert message_bytes == new_message_bytes


@given(x=strategies.input_map["packed_uint"])
def test_packed_uint_inverse(x):
    encoded = type_maps.ENCODERS["packed_uint"](x)
    decoded, pos = type_maps.DECODERS["packed_uint"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_int"])
def test_packed_int_inverse(x):
    encoded = type_maps.ENCODERS["packed_int"](x)
    decoded, pos = type_maps.DECODERS["packed_int"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_sint"])
def test_packed_sint_inverse(x):
    encoded = type_maps.ENCODERS["packed_sint"](x)
    decoded, pos = type_maps.DECODERS["packed_sint"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_fixed32"])
def test_packed_fixed32_inverse(x):
    encoded = type_maps.ENCODERS["packed_fixed32"](x)
    decoded, pos = type_maps.DECODERS["packed_fixed32"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_sfixed32"])
def test_packed_sfixed32_inverse(x):
    encoded = type_maps.ENCODERS["packed_sfixed32"](x)
    decoded, pos = type_maps.DECODERS["packed_sfixed32"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_float"])
def test_packed_float_inverse(x):
    encoded = type_maps.ENCODERS["packed_float"](x)
    decoded, pos = type_maps.DECODERS["packed_float"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_fixed64"])
def test_packed_fixed64_inverse(x):
    encoded = type_maps.ENCODERS["packed_fixed64"](x)
    decoded, pos = type_maps.DECODERS["packed_fixed64"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_sfixed64"])
def test_packed_sfixed64_inverse(x):
    encoded = type_maps.ENCODERS["packed_sfixed64"](x)
    decoded, pos = type_maps.DECODERS["packed_sfixed64"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


@given(x=strategies.input_map["packed_double"])
def test_packed_double_inverse(x):
    encoded = type_maps.ENCODERS["packed_double"](x)
    decoded, pos = type_maps.DECODERS["packed_double"](encoded, 0)
    assert isinstance(encoded, bytearray)
    assert pos == len(encoded)
    assert x == decoded


def test_seen_repeated():
    # 确保 seen_repeated 被设置并保留
    config = Config()

    message = {"1": [1, 2, 3], "2": [{"1": 1}, {"1": 1}]}
    typedef = {
        "1": {"type": "int"},
        "2": {"type": "message", "message_typedef": {"1": {"type": "int"}}},
    }

    # 确保我们为包含多个项目的列表设置了 seen_repeated
    encoded = length_delim.encode_lendelim_message(
        message, config, TypeDef.from_dict(typedef)
    )
    decoded, typedef_out, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef.from_dict(typedef), 0
    )
    typedef_out = typedef_out.to_dict()
    assert "seen_repeated" in typedef_out["1"]
    assert typedef_out["1"]["seen_repeated"]
    assert "seen_repeated" in typedef_out["2"]
    assert typedef_out["2"]["seen_repeated"]

    message = {"1": 1, "2": {"1": 1}}
    encoded = length_delim.encode_lendelim_message(
        message, config, TypeDef.from_dict(typedef)
    )
    decoded, typedef_out, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef.from_dict(typedef), 0
    )
    typedef_out = typedef_out.to_dict()
    # 确保我们不为单个值设置 seen_repeated
    assert "seen_repeated" not in typedef_out["1"]
    assert "seen_repeated" not in typedef_out["2"]

    typedef["1"]["seen_repeated"] = True
    typedef["2"]["seen_repeated"] = True
    decoded, typedef_out, _, pos = length_delim.decode_lendelim_message(
        encoded, config, TypeDef.from_dict(typedef), 0
    )
    typedef_out = typedef_out.to_dict()
    # 确保我们保留 seen_repeated 并输出为列表
    assert "seen_repeated" in typedef_out["1"]
    assert typedef_out["1"]["seen_repeated"]
    # 确保输出为列表，即使只有一个元素
    assert isinstance(decoded["1"], list)

    assert "seen_repeated" in typedef_out["2"]
    assert typedef_out["2"]["seen_repeated"]
    # 确保输出为列表，即使只有一个元素
    assert isinstance(decoded["2"], list)


def test_immutable_typedef():
    # 确保原始 typedef 永远不会被解码操作修改
    config = Config()

    typedef0 = {
        "1": {"type": "int"},
        "2": {
            "type": "message",
            "message_typedef": {"1": {"type": "int"}},
            "alt_typedefs": {
                "2": "bytes",
                "3": {"1": {"type": "fixed64"}},
            },
        },
    }
    typedef0_deepcopy = copy.deepcopy(typedef0)
    message0 = {
        "1": 1,
        "2": {"1": 1},
    }
    data0 = length_delim.encode_lendelim_message(
        message0, config, TypeDef.from_dict(typedef0)
    )

    typedef1 = {
        "1": {"type": "int"},
        "2": {"type": "string"},
    }
    message1 = {
        "1": 5,
        "2": "Test123",
    }
    data1 = length_delim.encode_lendelim_message(
        message1, config, TypeDef.from_dict(typedef1)
    )

    length_delim.decode_lendelim_message(data1, config, TypeDef.from_dict(typedef0))
    assert typedef0 == typedef0_deepcopy

    typedef2 = {
        "1": {"type": "int"},
        "2": {
            "type": "message",
            "message_typedef": {"1": {"type": "int"}, "2": {"type": "int"}},
        },
        "3": {"type": "int"},
    }
    message2 = {
        "1": 7,
        "2": {
            "1": 1,
            "2": 3,
        },
        "3": 8,
    }
    data2 = length_delim.encode_lendelim_message(
        message2, config, TypeDef.from_dict(typedef2)
    )

    length_delim.decode_lendelim_message(data2, config, TypeDef.from_dict(typedef0))
    assert typedef0 == typedef0_deepcopy


@given(x=st.binary())
def test_bytes_fallback(x):
    # 确保即使我们的 default_binary_type 失败，也能回退到 bytes
    config = Config()
    config.default_binary_type = "string"

    encoded = length_delim.encode_bytes(x)
    decoded, pos = length_delim._try_decode_lendelim_fields(
        [encoded], FieldDef(1), config, []
    )
