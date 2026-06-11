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

import six
import struct
from blackboxprotobuf.lib.exceptions import BlackboxProtobufException

if six.PY3:
    from typing import Tuple

# gRPC over HTTP2 规范：https://github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md

HEADER_LEN = 1 + 4


def is_grpc(payload):
    # type: (bytes) -> bool
    if len(payload) < HEADER_LEN:
        return False
    if six.PY2 and isinstance(payload, bytearray):
        payload = bytes(payload)
    pos = 0
    while pos < len(payload):
        compression_byte = six.indexbytes(payload, pos)
        # 一旦我们支持压缩，将其改为支持 0x1
        if compression_byte != 0:
            return False
        message_length = struct.unpack_from(">I", payload[pos + 1 : pos + 5])[0]
        pos += message_length + 5

    if pos != len(payload):
        return False
    return True


def decode_grpc(payload):
    # type: (bytes) -> Tuple[bytes | list[bytes], str]
    """解码 GRPC。返回 protobuf 数据"""
    if six.PY2 and isinstance(payload, bytearray):
        payload = bytes(payload)

    if len(payload) == 0:
        raise BlackboxProtobufException("Error decoding GRPC. Payload is empty")

    pos = 0
    payloads = []
    while pos + HEADER_LEN <= len(payload):
        compression_byte = six.indexbytes(payload, pos)
        pos += 1
        if compression_byte != 0x00:
            if compression_byte == 0x01:
                # 负载已压缩
                # 如果负载已压缩，压缩方法在 `grpc-encoding` 头部中指定
                # 可选值为 "identity" / "gzip" / "deflate" / "snappy" / {自定义}
                raise BlackboxProtobufException(
                    "Error decoding GRPC. Compressed payloads are not supported"
                )
            else:
                raise BlackboxProtobufException(
                    "Error decoding GRPC. First byte must be 0 or 1 to indicate compression"
                )

        message_length = struct.unpack_from(">I", payload[pos : pos + 4])[0]
        pos += 4

        if len(payload) < pos + message_length:
            raise BlackboxProtobufException(
                "Error decoding GRPC. Payload length does not match encoded gRPC length"
            )

        payloads.append(payload[pos : pos + message_length])
        pos += message_length

    if pos != len(payload):
        raise BlackboxProtobufException(
            "Error decoding GRPC. Payload length does not match encoded gRPC lengths"
        )

    if len(payloads) > 1:
        return payloads, "grpc"
    else:
        return payloads[0], "grpc"


def encode_grpc(data, encoding="grpc"):
    # type: (bytes | list[bytes], str) -> bytes
    if encoding != "grpc":
        raise BlackboxProtobufException(
            "Error encoding GRPC with encoding %s. GRPC is only supported with no compression"
            % encoding
        )

    datas = data if isinstance(data, list) else [data]

    payload = bytearray()
    for data in datas:
        payload.append(0x00)  # 无压缩
        payload.extend(struct.pack(">I", len(data)))  # 长度
        payload.extend(data)

    return payload
