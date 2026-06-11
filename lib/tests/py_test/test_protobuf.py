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

from hypothesis import given, example, note
import hypothesis.strategies as st
import hypothesis
import strategies
import warnings
import base64
import json
import six

import bbpb_cn


warnings.filterwarnings(
    "ignore",
    "调用已弃用的 create 函数.*",
)

try:
    import Test_pb2
except:
    import os

    os.system(
        "cd tests/payloads; protoc --python_out ../py_test/ Test.proto; cd ../../"
    )
    import Test_pb2

testMessage_typedef = {
    "1": {"type": "double", "name": six.u("testDouble")},
    "2": {"type": "float", "name": six.u("testFloat")},
    # "4": {"type": "int", "name": "testInt32"},
    "8": {"type": "int", "name": six.u("testInt64")},
    # "16": {"type": "uint", "name": "testUInt32"},
    "32": {"type": "uint", "name": six.u("testUInt64")},
    # "64": {"type": "sint", "name": "testSInt32"},
    "128": {"type": "sint", "name": six.u("testSInt64")},
    "256": {"type": "fixed32", "name": six.u("testFixed32")},
    "512": {"type": "fixed64", "name": six.u("testFixed64")},
    "1024": {"type": "sfixed32", "name": six.u("testSFixed32")},
    "2048": {"type": "sfixed64", "name": six.u("testSFixed64")},
    # "4096": {"type": "int", "name": "testBool"},
    "8192": {"type": "string", "name": six.u("testString")},
    "16384": {"type": "bytes", "name": six.u("testBytes")},
    # "32768": {"type": "message", "name": "testEmbed",
    #          "message_typedef": {
    #                "3": {"type": "double", "name": "embedDouble"},
    #                "2": {"type": "bytes", "name": "embedString"}}
    # },
    # "65536": {"type": "packed_int", "name": "testRepeatedInt32"}
}


# 测试 bbpb_cn 解码
@given(x=strategies.gen_message_data(testMessage_typedef))
def test_decode(x):
    message = Test_pb2.TestMessage()
    for key, value in x.items():
        setattr(message, key, value)
    encoded = message.SerializeToString()
    decoded, typedef = bbpb_cn.decode_message(encoded, testMessage_typedef)
    bbpb_cn.validate_typedef(typedef)
    hypothesis.note("解码: %r" % decoded)
    for key in decoded.keys():
        assert x[key] == decoded[key]


# 测试 bbpb_cn 编码
@given(x=strategies.gen_message_data(testMessage_typedef))
def test_encode(x):
    encoded = bbpb_cn.encode_message(x, testMessage_typedef)
    message = Test_pb2.TestMessage()
    message.ParseFromString(encoded)

    for key in x.keys():
        assert getattr(message, key) == x[key]


# 尝试使用 blackbox 修改一个随机键并重新编码
# TODO: 将来做更多随机修改，比如交换整个值
@given(
    x=strategies.gen_message_data(testMessage_typedef),
    modify_num=st.sampled_from(sorted(testMessage_typedef.keys())),
)
def test_modify(x, modify_num):
    modify_key = testMessage_typedef[modify_num]["name"]
    message = Test_pb2.TestMessage()
    for key, value in x.items():
        setattr(message, key, value)
    encoded = message.SerializeToString()
    decoded, typedef = bbpb_cn.decode_message(encoded, testMessage_typedef)
    bbpb_cn.validate_typedef(typedef)

    # 排除 protobuf 默认值为 0 的情况
    hypothesis.assume(modify_key in decoded)

    if isinstance(decoded[modify_key], six.text_type):
        mod_func = lambda x: six.u("test")
    elif isinstance(decoded[modify_key], bytes):
        mod_func = lambda x: b"test"
    elif isinstance(decoded[modify_key], six.integer_types):
        mod_func = lambda x: 10
    elif isinstance(decoded[modify_key], float):
        mod_func = lambda x: 10
    else:
        hypothesis.note(
            "修改键失败: %s (%r)" % (modify_key, type(decoded[modify_key]))
        )
        assert False

    decoded[modify_key] = mod_func(decoded[modify_key])
    x[modify_key] = mod_func(x[modify_key])

    encoded = bbpb_cn.encode_message(decoded, testMessage_typedef)
    message = Test_pb2.TestMessage()
    message.ParseFromString(encoded)

    for key in decoded.keys():
        assert getattr(message, key) == x[key]


## 上述方法的第二个副本，使用 protobuf 与 json 互转的函数


@given(x=strategies.gen_message_data(testMessage_typedef))
@example(x={"testBytes": b"test123"})
@example(x={"testBytes": b"\x80"})
def test_decode_json(x):
    # 使用 JSON payload 测试
    message = Test_pb2.TestMessage()
    for key, value in x.items():
        setattr(message, key, value)
    encoded = message.SerializeToString()

    decoded_json, typedef_json = bbpb_cn.protobuf_to_json(
        encoded, testMessage_typedef
    )
    bbpb_cn.validate_typedef(typedef_json)
    hypothesis.note("编码 JSON:")
    hypothesis.note(decoded_json)
    decoded = json.loads(decoded_json)
    hypothesis.note("原始值:")
    hypothesis.note(x)
    hypothesis.note("解码值:")
    hypothesis.note(decoded)
    for key in decoded.keys():
        if key == "testBytes":
            decoded[key] = six.ensure_binary(decoded[key], encoding="latin1")
        assert x[key] == decoded[key]


@given(x=strategies.gen_message_data(testMessage_typedef))
@example(x={"testBytes": b"\x80"})
def test_encode_json(x):
    # 使用 JSON payload 测试
    if "testBytes" in x:
        x["testBytes"] = x["testBytes"].decode("latin1")
    json_str = json.dumps(x)

    hypothesis.note("JSON 字符串输入:")
    hypothesis.note(json_str)
    hypothesis.note(json.loads(json_str))

    encoded = bbpb_cn.protobuf_from_json(json_str, testMessage_typedef)
    assert not isinstance(encoded, list)
    hypothesis.note("BBP 解码:")

    test_decode, _ = bbpb_cn.decode_message(encoded, testMessage_typedef)
    hypothesis.note(test_decode)

    message = Test_pb2.TestMessage()
    message.ParseFromString(encoded)
    hypothesis.note("消息:")
    hypothesis.note(message)

    for key in x.keys():
        hypothesis.note("消息值")
        hypothesis.note(type(getattr(message, key)))
        hypothesis.note("原始值")
        hypothesis.note(type(x[key]))
        if key == "testBytes":
            x[key] = six.ensure_binary(x[key], encoding="latin1")
        assert getattr(message, key) == x[key]


@given(
    x=strategies.gen_message_data(testMessage_typedef),
    modify_num=st.sampled_from(sorted(testMessage_typedef.keys())),
)
def test_modify_json(x, modify_num):
    modify_key = testMessage_typedef[modify_num]["name"]
    message = Test_pb2.TestMessage()
    for key, value in x.items():
        setattr(message, key, value)
    encoded = message.SerializeToString()
    decoded_json, typedef = bbpb_cn.protobuf_to_json(
        encoded, testMessage_typedef
    )
    bbpb_cn.validate_typedef(typedef)
    decoded = json.loads(decoded_json)

    # 排除 protobuf 默认值为 0 的情况
    hypothesis.assume(modify_key in decoded)

    if isinstance(decoded[modify_key], six.text_type):
        mod_func = lambda x: six.u("test")
    elif isinstance(decoded[modify_key], bytes):
        mod_func = lambda x: b"test"
    elif isinstance(decoded[modify_key], six.integer_types):
        mod_func = lambda x: 10
    elif isinstance(decoded[modify_key], float):
        mod_func = lambda x: 10
    else:
        hypothesis.note(
            "修改键失败: %s (%r)" % (modify_key, type(decoded[modify_key]))
        )
        assert False

    decoded[modify_key] = mod_func(decoded[modify_key])
    x[modify_key] = mod_func(x[modify_key])

    encoded = bbpb_cn.protobuf_from_json(
        json.dumps(decoded), testMessage_typedef
    )
    assert not isinstance(encoded, list)
    message = Test_pb2.TestMessage()
    message.ParseFromString(encoded)

    for key in decoded.keys():
        hypothesis.note("消息值:")
        hypothesis.note(type(getattr(message, key)))
        hypothesis.note("原始值:")
        hypothesis.note((x[key]))
        if key == "testBytes":
            x[key] = six.ensure_binary(x[key], encoding="latin1")
        assert getattr(message, key) == x[key]
