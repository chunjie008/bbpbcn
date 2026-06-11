"""BlackboxProtobuf 的异常类"""

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

if six.PY3:
    from typing import Any, Optional, List


class BlackboxProtobufException(Exception):
    """Blackbox Protobuf 引发的异常的基类"""

    def __init__(self, message, path=None, *args):
        # type: (str, Optional[List[str]], Any) -> None
        self.path = path
        super(BlackboxProtobufException, self).__init__(message, *args)

    def set_path(self, path):
        # type: (BlackboxProtobufException, List[str]) -> None
        if self.path is None:
            self.path = path


class TypedefException(BlackboxProtobufException):
    """当类型定义中识别出错误时抛出，例如冲突或不一致的值。"""

    def __str__(self):
        # type: (TypedefException) -> str
        message = super(TypedefException, self).__str__()
        if self.path is not None:
            message = (
                "Encountered error within typedef for field %s: "
                % "->".join(map(str, self.path))
            ) + message
        else:
            message = ("Encountered error within typedef: ") + message
        return message


class EncoderException(BlackboxProtobufException, ValueError):
    """当将字典编码为类型定义时出错时抛出"""

    def __str__(self):
        # type: (EncoderException) -> str
        message = super(EncoderException, self).__str__()
        if self.path is not None:
            message = (
                "Encountered error encoding field %s: " % "->".join(map(str, self.path))
            ) + message
        else:
            message = ("Encountered error encoding message: ") + message
        return message


class DecoderException(BlackboxProtobufException, ValueError):
    """当将字节串解码为字典时出错时抛出"""

    def __str__(self):
        # type: (DecoderException) -> str
        message = super(DecoderException, self).__str__()
        if self.path is not None:
            message = (
                "Encountered error decoding field %s: " % "->".join(map(str, self.path))
            ) + message
        else:
            message = ("Encountered error decoding message: ") + message
        return message


class ProtofileException(BlackboxProtobufException):
    def __init__(self, message, path=None, filename=None, *args):
        # type: (ProtofileException, str, Optional[List[str]], Optional[str], Any) -> None
        self.filename = filename
        super(BlackboxProtobufException, self).__init__(message, path, *args)

    def __str__(self):
        # type: (ProtofileException) -> str
        message = super(ProtofileException, self).__str__()
        if self.path is not None:
            message = (
                "Encountered error within protofile %s for field %s: "
                % (self.filename, "->".join(map(str, self.path)))
            ) + message
        else:
            message = (
                "Encountered error within protofile %s: " % self.filename
            ) + message

        return message
