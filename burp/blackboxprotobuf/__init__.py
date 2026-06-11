# 版权所有 (c) 2018-2023 NCC Group Plc
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

import os
import sys
import inspect

# 将正确的目录添加到 sys.path
_BASE_DIR = os.path.abspath(
    os.path.dirname(inspect.getfile(inspect.currentframe())) + "../../../"
)

sys.path.insert(0, _BASE_DIR + "/lib/")
sys.path.insert(0, _BASE_DIR + "/burp/deps/six/")
sys.path.insert(0, _BASE_DIR + "/burp/deps/protobuf/python/")

# extend_path 会在 sys.path 中查找其他 'blackboxprotobuf' 模块并将它们添加到 __path__
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)


# 修复在 Jython 中加载 protobuf 库的 Hack 方法。参见 https://github.com/protocolbuffers/protobuf/issues/7776
def fix_protobuf():
    import six

    u = six.u

    def new_u(s):
        if s == r"[\ud800-\udfff]":
            # 不匹配任何内容
            return "$^"
        else:
            return u(s)

    six.u = new_u


fix_protobuf()

# 镜像 lib 中的操作，以便我们可以使用 blackboxprotobuf.<function>
from blackboxprotobuf.lib.api import *
