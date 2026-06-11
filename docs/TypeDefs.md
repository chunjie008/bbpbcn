# 类型定义

类型定义（也称为 typedef）是 BBPB 用来存储消息及其字段元数据的数据结构。它包含每个字段的确切类型以及字段名称等其他元数据。

## 解码

解码消息时，typedef 是**可选**的。如果提供了字段类型和名称，解码时会使用它们，但如果没有 typedef 或 typedef 不包含某字段的元数据，BBPB 会根据该字段的 "wire type"（见下方的 Wire Types）选择默认类型。

解码时 BBPB 猜测的默认类型可能与实际类型不匹配，仅是一种尽力而为的猜测。用户可能需要使用 typedef 将类型改为正确的值。

解码函数会返回一个类型定义，其中包含解码消息中每个字段编号所使用的类型。这些类型是重新编码消息所必需的。如果向解码器提供了 typedef，解码函数会返回该 typedef 的副本，并为任何未知字段添加类型值。

## 编码

将消息编码回 protobuf 消息时，typedef 是**必需**的。它包含编码器将每个消息字段映射到正确二进制表示所需的数据。如果消息包含不在 typedef 中的字段，将引发异常。

在大多数情况下，应向编码器提供解码器返回的确切类型定义。在编码前修改类型定义可能导致意外的数据类型不匹配和不一致的编码错误。如果你想更改消息中字段的类型，应使用修改后的 typedef 重新解码消息。

## 类型定义格式

类型定义是一个 Python 字典/JSON 对象，其中每个键是字段编号，值是字段的元数据（称为字段定义）。

例如：

~~~
{
    "1": { "name": "email",
           "type": "string",
         },
    "2": { "name": "uid",
           "type": "int",
         },
    "3": {
           "type": "string",
         }
}
~~~

字段定义可以包含以下字段：

### `type`（必需）

type 字段是必需字段，应包含该字段的 BBPB 类型。这些类型大致映射到 protobuf 类型，但可能不完全一致。

以下是有效的 BBPB 类型：
- `uint`
- `int`
- `sint`
- `fixed32`
- `sfixed32`
- `float`
- `fixed64`
- `sfixed64`
- `double`
- `bytes`
- `bytes_hex`
- `string`
- `message`
- `packed_uint`
- `packed_int`
- `packed_sint`
- `packed_fixed32`
- `packed_sfixed32`
- `packed_float`
- `packed_fixed64`
- `packed_sfixed64`
- `packed_double`

最新的类型列表也可在 [type_maps.py](/lib/bbpb_cn/lib/types/type_maps.py) 中找到。

### `name`

字段的用户友好名称，可在解码消息中替代字段编号使用。如果名称为空字符串（`""`），则被忽略。

### `message_typedef`

如果 `type` 是 `message`，则需要 `message_typedef` 或 `message_type_name` 其中之一。`message` 类型表示该字段包含一个子消息。此字段包含用于编码/解码子消息的类型定义。

### `message_type_name`

该字段是 `message_typedef` 的替代方案，应引用 `config.known_types` 中的另一个类型定义。`known_types` 中的类型定义将用于该字段，而不是嵌入的类型定义。这可以大大简化类型定义，并允许在不同消息之间复用类型定义。

### `alt_typedefs`

`alt_typedefs` 字段是一个字典，包含 `message` 类型字段的"替代"类型/类型定义。

通常，protobuf 不允许单个字段编号具有不同的类型——无论是在同一消息中还是跨多个相同类型的消息。然而，一种常见模式是使用 `bytes` 类型（而非特定的消息类型）来嵌入另一个 protobuf 消息。这种模式由 `google.protobuf.Any` 类型推广，详见 <https://protobuf.dev/programming-guides/proto3/#any>。

这意味着使用相同消息类型编码的两个 protobuf 消息可能包含完全不同类型的内嵌消息，而 BBPB 无法确定使用了哪种类型或预测未来消息的类型。

处理这些消息的"技术上正确"的方法是将类型设置为 `bytes` 并不解码内嵌消息，但这不太实用。相反，如果 BBPB 对某个字段已经有 `message_typedef`，并且该 `message_typedef` 无法有效解码该字段的某个实例，它将尝试使用 `alt_typedefs` 中的任何类型定义。如果 `alt_typedefs` 中没有可用的类型定义，BBPB 会向 `alt_typedefs` 中添加新的类型定义。

替代类型定义从 `1` 开始编号，其中 `0` 通常指存储在 `message_typedef` 中的主要类型定义。在解码器输出中，替代类型定义编号会放在字段名称或编号后的 `-` 后面，以指示使用了哪个定义来解码该字段，从而指示应使用哪个定义来重新编码。

例如，消息中的 `{"1-2": { ... }}` 表示字段编号 `1` 是用 `alt_typedefs[2]` 解码的。也可以使用字段名称代替字段编号，如 `{"user_profile-2": { ... }}`。

在极少数情况下，`alt_typedef` 字典可以包含一个类型字符串（如 `string` 或 `bytes`）而不是类型定义。这仅当创建 typedef 时字段包含可解码消息，但 BBPB 在后续运行时未能识别为有效的 protobuf 消息时才会发生。

### `field_order`

Field order 包含 protobuf 子消息中字段被解码的顺序。这有助于 BBPB 避免意外改变被错误解码为消息的字节字段，但对于合法的 protobuf 消息通常不需要。

此字段可以通过设置 `config.preserve_field_order` 为 `False` 来禁用。

### `example_value_ignored`

该字段可能包含解码后的 protobuf 消息中的示例值。仅用于帮助在 typedef 中识别正确的字段编号进行编辑，编码和解码过程中会被忽略。

## Wire Types

protobuf 二进制数据不包含数据字段的确切类型信息。每个编码后的字段都有一个字段编号和一个 "wire type"。Wire type 告诉解码器如何确定字段的长度。这对于向后兼容非常重要，因为它允许解码器跳过其无法识别的字段，同时仍能解析消息的其余部分。

更多信息请参见 <https://protobuf.dev/programming-guides/encoding/#structure>。

Protobuf 定义了以下 wire type：

- Varint：可变长整数表示，每个字节用一位来指示是否为最后一个字节
- Fixed 64 bit：64 位数字，可以是整数或浮点数
- Fixed 32 bit：32 位数字，可以是整数或浮点数
- Length Delimited：字段数据前有一个包含数据长度的 varint
- Start/End Group：本身不是字段，而是将一组字段用标签包裹在一起。已弃用，建议使用子消息，BBPB 不支持

基于 wire type，BBPB 可以猜测每个字段的正确类型，同时确保字段可以重新编码为有效的 protobuf。

## 修改 TypeDefs
### 更改字段类型

可以通过修改 typedef 中的 "type" 字段来纠正单个字段的类型，然后使用修改后的 typedef 重新解码 protobuf 数据。避免直接将修改后的 typedef 用于编码器函数（而不是重新解码），因为这可能产生不一致的 protobuf 数据。

修改后的类型必须与 typedef 中原始类型具有相同的 wire type，否则 typedef 对原始 protobuf 数据将无效。例如，你可以将 `int` 值改为 `sint` 以使用 zigzag 编码，但不能将其改为 `float` 或 `double`。

#### Varint 类型

Varint wire type 是一种可变长整数编码。每个字节用一位来指示是否还有后续字节或这是最后一个字节。

Varint 可以映射到几种 BBPB 类型：

- `int`（默认）— 可以表示正数和负数
    - 负值使用补码表示，这意味着负数的最高位必须设置
    - 补码需要最大数量的 varint 字节来表示负数，如果负值常见则效率低
    - 这是默认值，因为它能正确表示大多数无符号整数，即使原始类型是 `uint`
- `uint` — 无符号整数，可以表示比 `int` 更大的值
    - 如果 BBPB 解码出负数而它们应该始终为正，可选择此类型
- `sint` — 通过 Zigzag 编码可以表示正数和负数
    - Zigzag 编码通过正负交替将无符号整数映射到有符号整数。例如，0 -> 0, 1 -> -1, 2 -> +1, 3 -> -2, ...
    - 比 `int` 更高效地表示小的负数，因为像 `-1` 这样的值只需一个字节编码，而不是 varint 的最大字节数
    - 如果解码后的数值与预期值大约相差 2 倍，或数值被解码为正数而本应是负数，可选择此类型

BBPB 中没有专门的布尔类型，但布尔值被编码为 varint，值为 0 表示 False，1 表示 True。

更多关于 varint 编码的信息，请参见 <https://protobuf.dev/programming-guides/encoding/#varints> 和 <https://protobuf.dev/programming-guides/encoding/#int-types>。

#### Fixed 64 类型

Fixed 64 wire type 表示该字段始终为 64 位。可用于表示浮点数以及有符号或无符号整数。

有效的类型：
- `fixed64`（默认）— 无符号 64 位整数
- `sfixed64` — 有符号 64 位整数
- `double` — 64 位浮点数

默认值是整数类型。`double` 作为默认选择可能更合理，但在全局更改之前需要进一步研究。参见"更改默认类型"了解如何在每个项目的基础上更改默认值。

#### Fixed 32 类型

Fixed 32 wire type 表示该字段始终为 32 位。可用于表示浮点数以及有符号或无符号整数。

有效的类型：
- `fixed32`（默认）— 无符号 32 位整数
- `sfixed32` — 有符号 32 位整数
- `float` — 32 位浮点数

默认值是整数类型。`float` 作为默认选择可能更合理，但在全局更改之前需要进一步研究。参见"更改默认类型"了解如何在每个项目的基础上更改默认值。

#### Length Delimited 类型

Length delimited wire type 表示字段以一个 varint 开头，该 varint 表示字段的字节长度。此 wire type 是最广泛的，可以表示多种字段类型，包括内嵌消息、字符串、字节和 packed 字段。

BBPB 不会为 length delimited 字段使用单一默认类型，而是首先尝试将字段解码为 `message`，如果解码失败则回退到 `string`，如果 `string` 也失败则最终回退到 `bytes`。

有效的类型：
- `message` — 字节表示一个编码后的 protobuf 消息
    - 内嵌消息的类型定义存储在 `message_typedef` 字段中
    - 或者，`message_type_name` 字段可用于引用另一个命名 typedef，而无需嵌入整个 typedef
- `bytes` — 直接作为 Python bytes 解析字段数据，可以表示任何 length delimited 字段
- `bytes_hex` — 与 bytes 相同，但使用十六进制编码为字符串
- `string` — 表示 UTF-8 或 ASCII 字符串
- `packed_*` — Packed 字段是一种更高效的表示重复值（如列表或数组）的机制，通过在编码时移除重复的 tag（包含字段编号和 wire type 的 varint）来实现。
    - BBPB 支持以下 packed 类型：
        - `packed_uint`
        - `packed_int`
        - `packed_sint`
        - `packed_fixed32`
        - `packed_sfixed32`
        - `packed_float`
        - `packed_fixed64`
        - `packed_sfixed64`
        - `packed_double`
    - BBPB 没有检测 packed 字段的机制，这些类型必须由用户明确设置。

更多关于 length delimited 编码的信息，请参见 <https://protobuf.dev/programming-guides/encoding/#length-types>。

### 更改默认类型

虽然编辑类型定义可以用来更改现有字段的类型，但也可以更改特定 wire type 使用的默认类型。更改默认类型必须遵循与类型编辑相同的规则：新类型的 wire type 必须与原始 wire type 相同。

wire type 的默认类型可以通过向解码器提供 `Config` 对象并使用 `default_types` 字典（位于 [config.py](/lib/bbpb_cn/lib/config.py#L49)）覆盖默认类型来修改。字典的键是 wire type，可以在 [wiretypes.py](/lib/bbpb_cn/lib/types/wiretypes.py) 中找到，并与 <https://protobuf.dev/programming-guides/encoding/#structure> 中的 wire type 匹配。

例如：

~~~
config.default_types[wiretypes.FIXED64] = 'double'
~~~

`Config` 中的 `default_types` 字段不用于 length delimited 类型，因为 length delimited 字段有特殊的回退逻辑。对于这些字段，你可以通过更改 `Config` 对象上的 `default_binary_type`（位于 [/lib/bbpb_cn/lib/config.py#L45](/lib/bbpb_cn/lib/config.py#L45)）来替换 `bytes` 回退类型。但与默认类型不同，解码器在回退到 `default_binary_type` 之前仍会尝试将字段解码为消息或字符串。

默认二进制类型主要用于允许更改二进制表示，例如 `bytes_hex` 而不是 `bytes`，但也可用于默认尝试 packed 类型。

### 命名字段

默认情况下，解码后的消息将使用字段编号作为字典键。但是，用户可以通过修改 "name" 字段为字段添加更具可读性的名称。

"name" 字段将用作解码消息中的字典键。编码器接受原始字段编号或 typedef 的 "name" 字段中指定的名称。字段名称需要唯一，应为字母数字加下划线，但不能以数字开头（参见 [api.py](/lib/bbpb_cn/lib/api.py#L310) 中的正则表达式）。

### 从头创建类型定义和字段

虽然 BBPB 的许多工作流程都是围绕编辑解码器生成的类型定义展开的，但仍可以手动添加新字段或从头创建新的类型定义。

要向现有 typedef 添加新的 protobuf 字段，只需向 typedef 字典（顶层字典或 `message_typedef` 字典内）添加新的键，并添加适当的 `type` 字段。`name` 字段是可选的，但会大大提升可读性。

例如：

~~~
{
    "1": { ...（现有字段编号）... },
    "5": {
        "name": "uid",
        "type": "int"
    }
}
~~~

或：

~~~
typedef["5"] = {
    "name": "uid",
    "type": "int"
}
~~~

如果 `type` 是 `message`，则还需要 `message_typedef` 或 `message_type_name` 其中之一。`message_typedef` 应包含表示该字段类型定义的字典。

如果你从其他来源知道 protobuf 的字段，则可以从头创建类型定义。只需为顶层消息类型定义创建一个字典，其中每个键是包含字段编号的字符串，每个条目的值是包含字段信息的字典。

每个 protobuf 字段都需要有一个 `type` 属性，包含 BBPB 类型。`name` 属性是可选的，但建议用于可读性。

### 清理 Typedefs

如果类型定义将保存供重用或嵌入到代码中，可以清理它以提升可读性并最小化定义的大小。

任何未从默认值修改过的字段编号都可以从定义中或任何 `message_typedefs` 中移除。要移除字段，请从 typedef 字典中删除字典键和关联值。

所有剩余的字段编号都需要有一个 `type` 属性，所有 `message` 字段需要 `message_typedef` 或 `message_type_name`。

`name` 属性不是必需的，如果为空可以移除，但建议保留。

如果 `alt_typedef` 中的定义未被自定义过，则可以移除。

typedef 上的任何其他属性都可以移除，包括：
- `example_value_ignored`
- `field_order`
