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

""" payloads 模块旨在处理 protobuf 数据的不同编码方式，
    例如压缩和 grpc 头部。 """

from blackboxprotobuf.lib.exceptions import BlackboxProtobufException
from . import gzip, grpc

import six

if six.PY3:
    from typing import List, Callable, Tuple, Optional


# 返回一个有序的潜在解码器列表，从最具体到最不具体
# 使用者应遍历每个解码器，尝试解码，然后尝试
# 解码为 protobuf。这应尽量减少任何解码器的
# 误报概率
def find_decoders(buf):
    # type: (bytes) -> List[Callable[[bytes], Tuple[bytes | list[bytes], str]]]
    # 将来，我们也可以考虑 content-type，例如
    # grpc，但这有误报的风险
    decoders = []  # type: List[Callable[[bytes], Tuple[bytes | list[bytes], str]]]

    if gzip.is_gzip(buf):
        decoders.append(gzip.decode_gzip)

    if grpc.is_grpc(buf):
        decoders.append(grpc.decode_grpc)

    decoders.append(_none_decoder)
    return decoders


def _none_decoder(buf):
    # type: (bytes) -> Tuple[bytes, str]
    return buf, "none"


# 按名称解码
def decode_payload(buf, decoder):
    # type: (bytes, Optional[str]) -> Tuple[bytes | list[bytes], str]
    if decoder is None:
        return buf, "none"
    decoder = decoder.lower()
    if decoder == "none":
        return buf, "none"
    elif decoder.startswith("grpc"):
        return grpc.decode_grpc(buf)
    elif decoder == "gzip":
        return gzip.decode_gzip(buf)
    else:
        raise BlackboxProtobufException("Unknown decoder: " + decoder)


# 按名称编码，应传入 decode 函数的结果
def encode_payload(buf, encoder):
    # type: (bytes | list[bytes], Optional[str]) -> bytes
    if encoder is None:
        encoder = "none"

    encoder = encoder.lower()
    if encoder == "none":
        if isinstance(buf, list):
            raise BlackboxProtobufException(
                "Cannot encode multiple buffers with none/missing encoding"
            )
        return buf
    elif encoder.startswith("grpc"):
        return grpc.encode_grpc(buf, encoder)
    elif encoder == "gzip":
        return gzip.encode_gzip(buf)
    else:
        raise BlackboxProtobufException("Unknown encoder: " + encoder)
