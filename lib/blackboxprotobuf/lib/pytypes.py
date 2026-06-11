"""此模块提供顶层类型，用于向 blackboxprotobuf 库添加类型定义。"""

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
    from typing import Any, Dict, List, TypedDict

    # 消息可以包含任何值
    # 我们定义的函数可能有固定类型，但有人可能添加一个
    # 输出任意对象的类型函数
    Message = Dict[str | int, Any]

    TypeDefDict = Dict[str, "FieldDefDict"]

    FieldDefDict = TypedDict(
        "FieldDefDict",
        {
            "name": str,
            "type": str,
            "message_type_name": str,
            "message_typedef": TypeDefDict,
            "alt_typedefs": Dict[str, str | TypeDefDict],
            "example_value_ignored": Any,
            "seen_repeated": bool,
            "field_order": List[str],
        },
        total=False,
    )
