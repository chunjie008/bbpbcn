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

""" payloads 模块旨在处理 protobuf 数据的不同编码方式，
    例如压缩和 grpc 头部。 """

from bbpb_cn.lib.exceptions import bbpb_cnException
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
        raise bbpb_cnException("Unknown decoder: " + decoder)


# 按名称编码，应传入 decode 函数的结果
def encode_payload(buf, encoder):
    # type: (bytes | list[bytes], Optional[str]) -> bytes
    if encoder is None:
        encoder = "none"

    encoder = encoder.lower()
    if encoder == "none":
        if isinstance(buf, list):
            raise bbpb_cnException(
                "Cannot encode multiple buffers with none/missing encoding"
            )
        return buf
    elif encoder.startswith("grpc"):
        return grpc.encode_grpc(buf, encoder)
    elif encoder == "gzip":
        return gzip.encode_gzip(buf)
    else:
        raise bbpb_cnException("Unknown encoder: " + encoder)
