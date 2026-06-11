"""这些函数提供了 blackboxprotobuf Burp 扩展的钩子，
允许自定义某些功能以处理非标准应用。
"""

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


# 通用参数的文档：
#   content -- 请求的二进制内容
#   is_request -- 布尔值，True 表示请求，False 表示响应
#   content_info -- RequestInfo 或 ResponseInfo 对象，参见
#       https://portswigger.net/Burp/extender/api/burp/IRequestInfo.html 和
#       https://portswigger.net/Burp/extender/api/burp/IResponseInfo.html
#   helpers -- Burp 扩展助手，
#       https://portswigger.net/Burp/extender/api/burp/IExtensionHelpers.html
#   request/request_content_info -- 如果对响应调用，则发送相应的请求（用于检索 URL 参数）

# 有用的功能：
#    URL 参数：
#        for param in content_info.getParmeters():
#            if param.getName() == 'type':
#                ...
#    头部：
#        if 'content-type' in content_info.getHeaders():
#            ...
#    请求 Body：
#       body = content[content_info.getBodyOffset():].tostring()
#    设置参数：
#       import burp.IParameter
#       body = helpers.updateParameter(
#                   content,
#                   helpers.buildParameter('message',
#                                          protobuf_data,
#                                          IParameter.PARAM_URL))


def detect_protobuf(content, is_request, content_info, helpers):
    """自定义对请求或响应的 protobuf 检测。如果是 protobuf 应返回 True，
    如果确定不是 protobuf 且不应尝试解码则返回 False，或返回 None
    以回退到标准的 content-type 头部检测。

    此函数可用于根据不同头部或客户应用功能添加 protobuf 检测。也可以使用 "return True"
    尝试解码每个请求/响应。
    """
    pass


def get_protobuf_data(
    content, is_request, content_info, helpers, request=None, request_content_info=None
):
    """自定义如何从请求中检索 protobuf 数据。默认情况下，
    假定请求/响应的 body 包含 protobuf payload 并尝试检测是否被压缩。

    如果 payload 位于非标准位置或具有非标准编码，可以使用此函数。
    它应返回消息中的原始 protobuf 字节。
    """
    pass


def set_protobuf_data(
    protobuf_data,
    content,
    is_request,
    content_info,
    helpers,
    request=None,
    request_content_info=None,
):
    """自定义如何在请求/响应中设置 protobuf 数据。此
    函数用于配置 protobuf 数据在请求中的位置以及如果消息被修改时的编码方式。例如，
    如果应用期望，则可以设置带有 base64 编码数据的查询参数。此函数是 `get_protobuf_data` 的镜像，
    如果一个函数被修改，另一个也应被修改。

    此函数应返回表示 HTTP 头部和 body 的字节，
    例如 Burp 助手的 `buildHttpMessage` 函数返回的内容
    (https://portswigger.net/burp/extender/api/burp/iextensionhelpers.html#buildHttpMessage)
    """
    pass


def hash_message(
    content, is_request, content_info, helpers, request=None, request_content_info=None
):
    """Blackbox protobuf 通过将类型定义保存在以"消息哈希"为键的字典中，
    来记住每个请求/响应应使用哪个类型定义。如果消息具有相同的哈希，
    它将尝试重用相同的类型定义。默认情况下，这是请求路径以及
    取决于它是请求还是响应的 true 或 false。

    如果消息类型与 URL 之间没有一对一的映射，则
    可以使用此函数自定义使用请求的哪些部分进行识别
    （例如消息类型头部或参数）。

    此函数应返回一个字符串。
    """
    pass
