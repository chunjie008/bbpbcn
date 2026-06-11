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

from .types import type_maps

import six
from blackboxprotobuf.lib.exceptions import (
    DecoderException,
)

if six.PY3:
    import typing

    if typing.TYPE_CHECKING:
        from typing import Dict
        from .pytypes import TypeDefDict


class Config:
    def __init__(self):
        # type: (Config) -> None
        # 消息类型名称到 typedef 的映射，之前存储在 `blackboxprotobuf.known_messages`
        self.known_types = {}  # type: Dict[str, TypeDefDict]

        # 非消息或字符串的"bytes"类对象的默认类型
        # 另一个选项目前只有 'bytes_hex'
        self.default_binary_type = "bytes"

        # 更改线类型的默认类型（例如，默认将 int 改为有符号，
        # 或将固定字段改为浮点数）
        self.default_types = {}  # type: Dict[int, str]

        # 配置 bbpb 是否应尝试按解码时的相同顺序重新编码字段
        # 字段顺序对于真正的 protobuf 来说应该不重要，
        # 但确保字节/字符串在解码/重新编码时不会意外地
        # 打乱恰好是有效 protobuf 的数据
        self.preserve_field_order = True

    def get_default_type(self, wiretype):
        # type: (Config, int) -> str
        default_type = self.default_types.get(wiretype, None)
        if default_type is None:
            default_type = type_maps.WIRE_TYPE_DEFAULTS.get(wiretype, None)

        if default_type is None:
            raise DecoderException(
                "Could not find default type for wire type %d" % wiretype
            )
        return default_type


default = Config()
