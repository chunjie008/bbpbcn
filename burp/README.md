# BlackBox Protobuf Burp 扩展

## 描述

这是一个用于拦截代理 Burp Suite (<https://portswigger.net/burp/>) 的扩展，允许编码和解码可能包含在拦截请求中的任意 protocol buffer (<https://developers.google.com/protocol-buffers/>) 消息。它设计用于在没有 protobuf 定义文件 (.proto) 的情况下工作——这类文件可能不可用，或无法与现有的 Burp 扩展一起使用。

关于 protobuf 解码的背景信息以及类型系统的详细说明和可能的类型边界情况，请参见库文档：
<https://github.com/nccgroup/blackboxprotobuf/blob/master/lib/README.md>

# 用法
## 安装

1. 如果尚未安装 Burp Suite，请从 <https://portswigger.net/burp/> 下载。
2. 下载/安装 Jython 2.7+，并配置 Burp 以指向其位置。参见 <https://portswigger.net/burp/help/extender.html#options_pythonenv>。
3. 克隆本仓库，然后运行 `git submodule update --init` 安装依赖。
4. 在 Burp 中，导航到 Extender -> Extensions，然后选择 "Add"。
5. 将 "Extension Type" 设置为 Python，并选择 git 仓库中的 `extender.py` 文件。
6. 点击 Next，扩展应该会加载。
7. **注意：** 支持 [gRPC](https://grpc.io/about/)，但你需要启用 Burp 的 HTTP/2 支持（在 Project Options->HTTP 下）。此外，目前只支持未压缩的 gRPC payload。如果 payload 的第一个字节不是 `0x00`，说明是被压缩的，你需要修改编/解码代码来处理。

## 编辑消息

每个内容类型为 "x-protobuf" 或 "application/protobuf" 的消息窗口都会新增一个标签页（可通过 `user_funcs.py` 配置）。protobuf 消息将被解析为 JSON 字典，以编号字段作为键。只要新值类型相同，就可以修改这些值。

上方的列表显示可用于解码此消息的命名类型定义列表。选择一个将使用新类型重新解码消息。Blackboxprotobuf 会尝试记住该端点最后选择的类型。`New` 按钮将当前类型定义保存为新名称。

"Validate" 按钮验证修改后的 JSON 消息能否重新编码。最好在切换到其他视图或发送消息之前使用此功能验证消息。如果你在 payload 无效的情况下切换标签页，将引发错误并重置为原始值。

"Edit Type" 打开一个窗口，用于以 JSON 格式编辑当前消息的类型定义。允许你更改类型或为字段命名。保存后，当前消息将使用新类型解码。如果你编辑了消息的默认类型定义，应使用 `New` 按钮保存，否则将在下一条消息时丢失。

"Reset Message" 按钮将 protobuf 消息恢复为原始解码值。`Clear Type` 按钮将重置为新的匿名类型定义。

## 编辑类型

消息的类型定义可以被修改，以使 protobuf 消息更易于使用。这允许你更改消息的解码方式（例如，将字段解码为 `sint` 而不是默认的 `int`），并允许你为字段分配名称以提高可读性。

字段编号不应修改，类型只能更改为同一 wire type 内的类型。完整的 wire type 和子类型列表如下。

类型定义中的 `example_value_ignored` 字段应包含消息中的一个值，以便更容易定位要修改的正确字段，但解析类型定义时会忽略该值本身。

### 类型参考
* Varint — 可变长整数（最多 8 字节）
    - `uint` — 无符号，高效表示正数，不能表示负数
    - `int` —（默认）有符号，但表示负数时效率低
    - `sint` — Zig-zag 编码，将有符号空间映射到无符号空间
* Fixed32 — 固定 32 位
    - `fixed32` —（默认）无符号整数
    - `sfixed32` — 有符号整数
    - `float` — 浮点数
* Fixed64 — 固定 64 位
    - `fixed64` —（默认）无符号整数
    - `sfixed64` — 有符号整数
    - `double` — 浮点数
* Length Delimited — 前有表示长度的 varint
    - `bytes` —（默认）原始数据，也用于字符串
    - `message` —（自动检测）Protobuf 消息。可包含嵌套类型定义（`message_typedef`）或标记类型名称（`message_type_name`）
    - `string` — 类似于 bytes，但返回 Python 字符串类型
    - `bytes_hex` — 将二进制数据输出为十六进制字符串而非转义字符串
    - `packed_*` — 相同类型的 repeated 字段打包到缓冲区。可与任何 Varint 或固定 wiretype 组合（例如 `packed_fixed32`）
* Group (Start/End)
    - `group` — 已弃用的字段分组方式。已被嵌套 Protobuf 消息取代。不支持

## Protobuf 类型编辑器标签页

任何保存过的命名消息定义都将显示在全局的 "Protobuf Type Editor Tab" 中。此标签页允许在没有活动请求/响应的情况下创建、重命名、编辑和删除类型定义。

"Save All Types"/"Load All Types" 按钮可用于将类型定义导出或导入为 JSON 文件。这可以确保类型安全备份或在实例之间共享。命名类型应在 Burp 重启后在扩展设置中持久保存，但如果已投入大量精力定制定义，建议定期备份。

最后，扩展会尝试导入/导出 `.proto` 文件。`.proto` 导出会尝试将所有已知类型定义保存为 protobuf 类型定义格式。你应该能够将 `.proto` 文件导入到其他期望原始类型定义的工具中。导入功能会尝试读取 `.proto` 文件并从中创建 Blackbox protobuf 类型定义。不支持 "import" 语句，任何被 import 语句引用的文件应先导入。导入和导出功能都比较粗糙，可能不适用于所有消息类型。

## 用户函数

扩展的某些行为可以通过 `burp/blackboxprotobuf/burp/user_funcs.py` 文件来更改。每个函数由扩展调用，以提供处理消息的替代方式：

* `detect_protobuf` — 自定义扩展如何判断请求/响应是否为 protobuf 消息。默认情况下，扩展检查几个 content-type 头部来决定何时将请求/响应解析为 protobuf。此函数可用于检查其他头部、参数，或直接对所有消息返回 True。如果是 protobuf 应返回 `True`，否则返回 `False`，或返回 `None` 以回退到 content-type 检查。
* `get_protobuf_data` — 自定义从消息中获取数据的过程。默认情况下，扩展从消息体中获取二进制数据。此函数可用于从其他位置（如头部或参数）获取数据。也可用于解析非默认编码。应返回 protobuf 数据。
* `set_protobuf_data` — 自定义 protobuf 数据重新编码后如何存回请求/响应。应与 `get_protobuf_data` 对称，仅在 `get_protobuf_data` 被自定义时需要。
* `hash_message` — 自定义扩展如何识别请求/响应使用哪种消息类型。默认情况下，扩展使用路径和请求/响应类型的组合。如果应用程序有更好的指示器，例如 `MessageType` 头部或参数，则此函数可以将其作为键返回。返回值仅用作字典/hashmap 的键，因此可以是任意值，但应为字符串值以便序列化为 JSON 进行持久化。
