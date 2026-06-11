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

import grpc
from concurrent import futures


import Test_pb2_grpc


class TestService(Test_pb2_grpc.TestService):
    def TestRPC(self, msg, ctx):
        print("收到 RPC 消息: %s" % msg)
        return msg


def serve():
    with open("key.pem", "rb") as f:
        ssl_key = f.read()
    with open("cert.pem", "rb") as f:
        ssl_cert = f.read()
    credentials = grpc.ssl_server_credentials([(ssl_key, ssl_cert)])

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    Test_pb2_grpc.add_TestServiceServicer_to_server(TestService(), server)
    server.add_secure_port("127.0.0.1:8000", credentials)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
