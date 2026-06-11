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

from hypothesis import assume, given, reproduce_failure, example
import hypothesis.strategies as st
import strategies
import pytest

from bbpbcn.lib import payloads
from bbpbcn.lib.payloads import grpc, gzip
from bbpbcn.lib.exceptions import bbpbcnException


def test_grpc():
    message = bytearray([0x00, 0x00, 0x00, 0x00, 0x01, 0xAA])
    data, encoding = grpc.decode_grpc(message)
    assert data == bytearray([0xAA])
    assert encoding == "grpc"

    # 压缩标志
    with pytest.raises(bbpbcnException):
        message = bytearray([0x01, 0x00, 0x00, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 未知标志
    with pytest.raises(bbpbcnException):
        message = bytearray([0x11, 0x00, 0x00, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 长度错误
    with pytest.raises(bbpbcnException):
        message = bytearray([0x00, 0x00, 0x01, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 长度错误
    with pytest.raises(bbpbcnException):
        message = bytearray([0x00, 0x00, 0x00, 0x00, 0x01, 0xAA, 0xBB])
        data = grpc.decode_grpc(message)

    # 空消息
    message = bytearray([0x00, 0x00, 0x00, 0x00, 0x00])
    data, encoding = grpc.decode_grpc(message)
    assert len(data) == 0
    assert encoding == "grpc"


@given(payloads=st.lists(st.binary(), min_size=2))
def test_grpc_multiple(payloads):
    # 测试包含多个 payload 的 grpc 编码

    # 手动编码多个 grpc payload 并将它们拼接在一起
    encoded = b""
    for payload in payloads:
        encoded += grpc.encode_grpc(payload)

    assert grpc.is_grpc(encoded)

    # 确保我们可以解码包含多个 grpc 的字节
    decoded, encoding = grpc.decode_grpc(encoded)
    assert isinstance(decoded, list)
    assert len(decoded) == len(payloads)

    for x, y in zip(decoded, payloads):
        assert x == y

    # 确保我们可以编码为相同的字节
    encoded2 = grpc.encode_grpc(decoded)
    assert encoded == encoded2


@given(data=st.binary())
def test_grpc_inverse(data):
    encoding = "grpc"
    encoded = grpc.encode_grpc(data)
    decoded, encoding_out = grpc.decode_grpc(encoded)

    assert data == decoded
    assert encoding == encoding_out


@given(data=st.binary())
def test_gzip_inverse(data):
    encoded = gzip.encode_gzip(data)
    decoded, encoding_out = gzip.decode_gzip(encoded)

    assert data == decoded
    assert "gzip" == encoding_out


@given(data=st.binary(), alg=st.sampled_from(["grpc", "gzip", "none"]))
def test_find_payload_inverse(data, alg):
    encoded = payloads.encode_payload(data, alg)
    decoders = payloads.find_decoders(encoded)

    valid_decoders = {}
    for decoder in decoders:
        try:
            decoded, decoder_alg = decoder(encoded)
            valid_decoders[decoder_alg] = decoded
        except:
            pass
    assert "none" in valid_decoders
    assert alg in valid_decoders
    assert valid_decoders[alg] == data
