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

from hypothesis import assume, given, reproduce_failure, example
import hypothesis.strategies as st
import strategies
import pytest

from blackboxprotobuf.lib import payloads
from blackboxprotobuf.lib.payloads import grpc, gzip
from blackboxprotobuf.lib.exceptions import BlackboxProtobufException


def test_grpc():
    message = bytearray([0x00, 0x00, 0x00, 0x00, 0x01, 0xAA])
    data, encoding = grpc.decode_grpc(message)
    assert data == bytearray([0xAA])
    assert encoding == "grpc"

    # 压缩标志
    with pytest.raises(BlackboxProtobufException):
        message = bytearray([0x01, 0x00, 0x00, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 未知标志
    with pytest.raises(BlackboxProtobufException):
        message = bytearray([0x11, 0x00, 0x00, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 长度错误
    with pytest.raises(BlackboxProtobufException):
        message = bytearray([0x00, 0x00, 0x01, 0x00, 0x01, 0xAA])
        data = grpc.decode_grpc(message)

    # 长度错误
    with pytest.raises(BlackboxProtobufException):
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
