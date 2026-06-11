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

import requests
import zlib
import Test_pb2
import struct


for payload_type in ["none", "gzip", "grpc"]:
    message = Test_pb2.TestMessage(testString="test123").SerializeToString()
    print(f"发送使用 {payload_type} 编码的 payload")
    if payload_type == "gzip":
        message = zlib.compress(message, level=9, wbits=31)
    elif payload_type == "grpc":
        # 伪 grpc 包装
        length = len(message)
        old_message = message
        message = bytearray()
        message.append(0x00)
        message.extend(struct.pack(">I", length))
        message.extend(old_message)

    response = requests.post(
        "http://localhost:8000",
        data=message,
        headers={
            "content-type": "application/protobuf",
            "payload_encoding": payload_type,
        },
        proxies={"http": "http://localhost:8080"},
    )
    print(f"收到响应: {response.status_code} {response.text}")
    response_content = response.content

    if payload_type == "gzip":
        response_content = zlib.decompress(response_content, wbits=31)
    elif payload_type == "grpc":
        old_response_content = response_content
        compression_byte = response_content[0]
        assert compression_byte == 0
        length = struct.unpack_from(">I", response_content[1:])[0]
        response_content = old_response_content[5:]
        assert length == len(response_content)

    response_message = Test_pb2.TestMessage()
    response_message.ParseFromString(response_content)

    print(f"收到响应消息: {response_message}")
