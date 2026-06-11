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
