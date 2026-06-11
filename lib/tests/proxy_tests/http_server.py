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

import Test_pb2
from http.server import BaseHTTPRequestHandler, HTTPServer
import zlib
import struct


class TestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload_type = self.headers.get("payload_encoding", "none")
        print(f"收到连接，payload 编码: {payload_type}")
        data = self.rfile.read1()
        if payload_type == "gzip":
            data = zlib.decompress(data, wbits=31)
        elif payload_type == "grpc":
            old_data = data
            compression_byte = data[0]
            assert compression_byte == 0
            length = struct.unpack_from(">I", data[1:])[0]
            data = old_data[5:]
            assert length == len(data)
        print("收到数据: %s" % data)
        message = Test_pb2.TestMessage()
        message.ParseFromString(data)
        print("收到消息: %s" % data)

        output = message.SerializeToString()

        if payload_type == "gzip":
            output = zlib.compress(output, level=9, wbits=31)
        elif payload_type == "grpc":
            # 伪 grpc 包装
            length = len(output)
            old_output = output
            output = bytearray()
            output.append(0x00)
            output.extend(struct.pack(">I", length))
            output.extend(old_output)

        self.send_response(200)
        self.send_header("content-type", "application/protobuf")
        self.send_header("content-length", len(output))
        self.end_headers()
        self.wfile.write(output)


server = HTTPServer(("", 8000), TestHandler)
server.serve_forever()
