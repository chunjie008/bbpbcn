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

from hypothesis import given, assume, note, example, reproduce_failure
import hypothesis.strategies as st
import collections
import strategies
import six
import binascii

from bbpb_cn.lib.config import Config
from bbpb_cn.lib.types import length_delim
from bbpb_cn.lib.types import type_maps
from bbpb_cn.lib.typedef import TypeDef


# 测试当替代 typedef 字符串为 unicode/string 时的 bug
def test_alt_typedef_unicode():
    config = Config()

    typedef = {
        "1": {"type": "message", "message_typedef": {}, "alt_typedefs": {"1": "string"}}
    }

    message = {"1-1": "test"}

    data = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))
    length_delim.decode_message(data, config, TypeDef.from_dict(typedef))

    # 也测试 unicode
    typedef = {
        "1": {"type": "message", "message_typedef": {}, "alt_typedefs": {"1": "string"}}
    }
    data = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))
    length_delim.decode_message(data, config, TypeDef.from_dict(typedef))


def test_alt_field_id_unicode():
    # 检查 Python2 中字段 ID 为 str 而非 unicode 时的 bug
    config = Config()

    typedef = {
        "1": {"type": "message", "message_typedef": {}, "alt_typedefs": {"1": "string"}}
    }

    message = {"1-1": "test"}

    data = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))
    length_delim.decode_message(data, config, TypeDef.from_dict(typedef))

    # 测试 unicode
    message = {"1-1": "test"}

    data = length_delim.encode_message(message, config, TypeDef.from_dict(typedef))
    length_delim.decode_message(data, config, TypeDef.from_dict(typedef))
