"""与 length_delim 或 protobuf 测试类似，但确保我们可以通过 JSON 编码/解码进行往返测试"""

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

from hypothesis import given, assume, note, example, reproduce_failure
import hypothesis.strategies as st
import strategies
import json
import six
import binascii

from bbpbcn.lib.config import Config
from bbpbcn.lib.types import length_delim
from bbpbcn.lib.types import type_maps
from bbpbcn.lib.typedef import TypeDef
from bbpbcn.lib.payloads import grpc, gzip
import bbpbcn


@given(x=strategies.gen_message())
def test_message_json_inverse(x):
    config = Config()
    typedef, message = x
    encoded = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))
    decoded_json, typedef_out = bbpbcn.protobuf_to_json(
        encoded, config=config, message_type=typedef
    )
    bbpbcn.validate_typedef(typedef_out)
    encoded_json = bbpbcn.protobuf_from_json(
        decoded_json, config=config, message_type=typedef_out
    )
    assert not isinstance(encoded_json, list)
    decoded, typedef_out = bbpbcn.decode_message(
        encoded_json, config=config, message_type=typedef
    )
    bbpbcn.validate_typedef(typedef_out)
    assert isinstance(encoded, bytearray)
    assert isinstance(decoded, dict)
    assert message == decoded


@given(x=strategies.gen_message(), n=st.integers(min_value=2, max_value=10))
def test_multiple_encoding(x, n):
    config = Config()
    typedef, message = x
    encoded = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))

    bufs = [encoded] * n
    message_json, typedef_out = bbpbcn.protobuf_to_json(bufs, typedef, config)
    messages = json.loads(message_json)
    assert isinstance(messages, list)
    assert len(messages) == n

    encoded2 = bbpbcn.protobuf_from_json(message_json, typedef, config)
    assert isinstance(encoded2, list)
    assert len(encoded2) == n


@given(x=strategies.gen_message(anon=True))
def test_anon_json_decode(x):
    """创建一个新的编码消息，然后尝试在没有 typedef 的情况下解码为 json，
    从 json 回到二进制，最后再将消息解码回原始格式。
    确保 json 解码能处理所有类型且不改变消息的内容。
    """
    config = Config()
    typedef, message = x
    encoded = bbpbcn.encode_message(
        message, config=config, message_type=typedef
    )
    decoded_json, typedef_out = bbpbcn.protobuf_to_json(
        encoded, config=config
    )
    bbpbcn.validate_typedef(typedef_out)
    note("JSON typedef: %r" % dict(typedef_out))
    encoded_json = bbpbcn.protobuf_from_json(
        decoded_json, config=config, message_type=typedef_out
    )
    assert not isinstance(encoded_json, list)
    decoded, typedef_out = bbpbcn.decode_message(
        encoded_json, config=config, message_type=typedef
    )
    bbpbcn.validate_typedef(typedef_out)
    note("原始消息: %r" % message)
    note("解码 JSON: %r" % decoded_json)
    note("解码消息: %r" % decoded)
    note("原始 typedef: %r" % typedef)
    note("解码 typedef: %r" % typedef_out)

    def check_message(orig, orig_typedef, new, new_typedef):
        for field_number in set(orig.keys()) | set(new.keys()):
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
            assert isinstance(orig_values, list)
            assert isinstance(new_values, list)

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
            note("新值: %r" % new_values)
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
    # assert message == decoded
