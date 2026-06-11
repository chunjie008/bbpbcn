# Copyright (c) 2018-2023 NCC Group Plc
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
