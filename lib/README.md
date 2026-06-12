# BlackBox Protobuf Library

## 描述

Blackbox protobuf 库是一个 Python 模块，用于在无法获取 protobuf 描述符文件的情况下解码和重新编码 protobuf 消息。该库提供了简单的 Python 接口来编码/解码消息，可集成到其他工具中。

该库主要面向渗透测试场景——修改消息至关重要，而 protocol buffer 定义可能不易获得。

## 背景

Protocol Buffers（protobuf）是 Google 发布的一种标准，附带有用于数据二进制序列化的库。Protocol buffers 由收发双方已知的 `.proto` 文件定义。实际的二进制消息不包含字段名或大部分类型信息。

对于每个字段，序列化后的 protocol buffer 包含两段元数据：字段编号（field number）和 wire type。Wire type 告诉解析器如何确定字段的长度，以便在字段未知时可以跳过它（protocol buffer 的设计目标之一是能够处理包含未知字段的消息）。单个 wire type 通常涵盖多种 protocol buffer 类型，例如长度分隔（length delimited）wire type 可用于 string、bytestring、内嵌消息或 packed repeated 字段。详见 <https://developers.google.com/protocol-buffers/docs/encoding#structure>。

protocol buffer 编译器（`protoc`）确实支持一种类似的无需定义文件的解码方式，即 `--decode_raw` 选项。但它不提供任何重新编码已解码消息的功能。

## 工作原理

该库根据提供的 wire type（偶尔也参考字段内容）做出最佳类型猜测，并构建可用于重新编码数据的类型定义。通常，大多数感兴趣的字段都会被解析成可用形式。用户可以选择传入自定义类型定义来覆盖猜测的类型。自定义类型定义还允许为字段命名以提高易用性。

# 使用
## 安装
包可以从源码安装：

```
poetry install
```

BlackBox Protobuf 也可以在 PyPi 上获取：<https://pypi.org/project/bbpbcn>。通过以下命令安装：

```
pip install --index-url https://test.pypi.org/simple/ bbpbcn
```

## CLI
该包定义了 `bbpbcn` 命令用于命令行编码/解码。

命令行用法参见 [CLI.md](./CLI.md)。

## 接口

主要的 `bbpbcn` 模块定义了一个 API，包含核心的编码/解码消息函数，以及多个便捷函数，用于简化 bbpbcn 在用户界面中的使用，例如直接编码/解码为 JSON 和验证修改后的类型定义。

### 解码
解码函数接受 protobuf 字节串，以及可选的类型定义或已知消息名称（映射到类型定义，位于 `bbpbcn.known_messages`）。如果未提供类型定义，则假设为空消息类型，所有类型从 protobuf 二进制数据推导。

解码器返回一个元组，包含解码数据的字典和生成的类型定义字典。如果输入类型定义未包含消息中所有字段的类型，输出类型定义将包含对这些字段的类型猜测。

使用示例：
```python
import bbpbcn
import base64

data = base64.b64decode('KglNb2RpZnkgTWU=')
message,typedef = bbpbcn.protobuf_to_json(data)
print(message)
```

### 编码
编码函数接受包含数据的 Python 字典和类型定义。与解码不同，类型定义是必需的，如果任何字段未定义则会失败。通常，类型定义应该是解码函数的输出或其修改版本。

使用示例：
```python
import bbpbcn
import base64

data = base64.b64decode('KglNb2RpZnkgTWU=')
message,typedef = bbpbcn.decode_message(data)

message['5'] = 'Modified Me'

data = bbpbcn.encode_message(message,typedef)
print(data)
```

### 类型定义结构
类型定义对象是一个 Python 字典，表示消息的类型结构，包含每个字段的类型和可选的名称。字典中的每个条目代表消息中的一个字段。键应为字段编号，值为包含属性的字典。

字典至少应包含 'type' 条目，其值为类型标识符字符串。有效的类型标识符可在 `bbpbcn/lib/types/type_maps.py` 中找到。

消息字段还将包含以下两个条目之一：'message_typedef' 或 'message_type_name'。'message_typedef' 应包含内嵌消息的第二个类型定义结构。'message_type_name' 应包含之前存储在 `bbpbcn.known_messages` 中的消息类型字符串标识符。如果两者都指定，'message_type_name' 将被忽略。

### JSON 编码/解码

`protobuf_to_json` 和 `protobuf_from_json` 函数是便捷函数，用于将消息编码/解码为 JSON 而非 Python 字典。这些函数专为用户面向的输入/输出而设计，会自动对输出排序，尝试编码字节串以便更好地打印，并在类型定义结构上注释示例值。

### 导出/导入 protofile

`export_protofile` 和 `import_protofile` 函数会尝试将 protobuffer `.proto` 文件转换为 bbpbcn 类型定义，反之亦然。这些函数提供了比 `bbpbcn.lib.protofile` 更高层次的接口（后者仅接受文件名）。protofile 函数未实现完整的解析器，可能在某些类型上失败。需要注意的一个常见情况是 ".proto" 文件中的 "import" 语句，不支持此功能。任何导入的文件必须先用 `import_protofile` 手动导入并保存在 `bbpbcn.known_messages` 中。

### 验证 Typedef

`validate_typedef` 函数用于对修改后的类型定义进行完整性检查，确保其内部一致且与之前的类型定义（如果提供）一致。这有助于捕获诸如将字段更改为不兼容的类型或重复字段名等问题。

### 输出辅助函数

`json_safe_transform` 是一个辅助函数，用于创建更可读的字节 JSON 输出。它会根据类型定义中的类型，以 `latin1` 编码/解码字节类型。

`sort_output` 是一个辅助函数，根据 typedef 中的字段编号对输出消息排序。这有助于使 JSON 输出更加一致和可预测。

`sort_typedef` 函数对 typedef 的字段进行排序，使输出更可读。消息字段按编号排序，类型字段（如 name、type、内嵌消息 typedef）排序时将重要的短字段置于顶部，特别是避免 name 和 type 字段被长内嵌 typedef 埋没。

### 配置

许多函数接受一个 `config` 关键字参数，类型为 `bbpbcn.lib.config.Config` 类。配置对象允许修改一些编码/解码功能并存储某些状态。这取代了之前为全局变量的一些配置。

目前包括：

* `known_types` — 消息类型名称到 typedef 的映射（之前为 `bbpbcn.known_messages`）

* `default_binary_type` — 更改解码未知字段时二进制字段的默认类型选择。默认为 `bytes`，但可设置为 `bytes_hex` 以返回十六进制编码的字符串。`bytes_base64` 将来可能是另一个选项。单个字段的类型始终可以通过更改 typedef 中的 `type` 来改变。

* `default_types` — 更改解码未知字段时任何 wiretype 的默认类型选择。例如，要默认将所有 varint 视为无符号整数，设置 `default_types[WIRETYPE_VARINT] = 'uint'`。

像 `bbpbcn.decode_message` 这样的 `api` 函数如果未指定配置，将默认使用全局的 `bbpbcn.lib.config.default` 对象。

## 类型详解

以下是 wire type 和默认值的快速参考。详见 <https://developers.google.com/protocol-buffers/docs/encoding> 以获取 Google 提供的更详细信息。

### 可变长整数 (varint)

`varint` wire type 使用多个字节表示整数，其中每个字节的一位用于指示是否为最后一个字节。这可用于表示整数（有符号/无符号）、布尔值或枚举。整数可以使用三种变体编码：

- `uint`：Varint 编码，不表示负数。
- `int`：标准编码，但对负数效率低（总是 10 字节）。
- `sint`：使用 ZigZag 编码，通过将负数映射到整数空间来高效表示负数。例如 -1 映射为 1，1 映射为 2，-2 映射为 3，依此类推。如果类型被误解且原始类型或错误类型是 `sint`，则可能导致数值大相径庭。

当前默认是 `int`，不使用 ZigZag 编码。

### Fixed32/64

固定长度 wire type 根据 wire type 具有隐式大小。这些类型支持固定大小的整数（有符号/无符号）或固定大小的浮点数（float/double）。默认类型是浮点类型，因为大多数整数更可能用 varint 表示。

### Length Delimited

长度分隔（length delimited）wire type 前有一个指示长度的 varint。这用于字符串、字节串、内嵌消息和 packed repeated 字段。消息通常可以通过验证是否为有效的 protobuf 二进制数据来识别。如果不是消息，默认类型是 string/byte，在 Python 中它们相对可互换。不同的默认类型（如 `bytes_hex`）可以通过更改 `bbpbcn.lib.types.default_binary_type` 来指定。

Packed repeated 字段是 `varint` 或固定长度 wire type 的数组。非 packed repeated 字段为每个元素使用单独的 tag（wire type + 字段编号），使其易于识别和解析。然而，packed repeated 字段只有一个初始的长度分隔 wire type tag。解析器需要已经知道完整类型才能解析各个元素。这使得这种字段类型难以与任意字节串区分，需要用户干预才能识别。在 protobuf 版本 2 中，repeated 字段必须在定义中显式声明为 packed。在 protobuf 版本 3 中，repeated 字段默认是 packed 的，可能会变得更加常见。
