# Blackbox Protobuf 命令行接口 (CLI)

## 描述

Blackbox Protobuf 库内置了 CLI 接口，可通过 `python -m bbpbcn` 调用，用于 shell 脚本、集成到其他工具或轻松解码任意的 protobuf 消息。

## 安装

Blackbox Protobuf 库可通过以下方式安装：

~~~
pip install bbpbcn
~~~

然后可以通过以下命令运行命令行接口：

~~~
bbpbcn
~~~

或

~~~
python3 -m bbpbcn
~~~

## 用法

### 示例

简单解码器：
~~~
cat test_data | bbpbcn -r
~~~

保存类型以便编辑：
~~~
cat test_data | bbpbcn -ot ./saved_type.json
~~~

使用类型解码：
~~~
cat test_data | bbpbcn -it ./saved_type.json
~~~

解码、编辑和重新编码：
~~~
cat test_data | bbpbcn  > message.json
vim message.json
cat message.json | bbpbcn -e > test_data_out
~~~

### 解码
CLI 解码模式（默认）接受 protobuf payload 和可选的类型定义，并输出一个包含解码消息和类型定义的 JSON 对象。

默认情况下，期望从 stdin 提供二进制 protobuf 消息。输入类型不能通过 stdin 提供，必须保存到文件并通过 `-it`/`--input-type` 参数提供。

或者，`-j`/`--json-protobuf` 参数允许将 protobuf 消息和 typedef 作为单个 JSON 对象传入。输入的 JSON 对象应包含 `protobuf_data` 字段（包含 base64 编码的 protobuf 数据），并可选项包含 `typedef` 字段（包含输入类型定义）。此选项对于调用 CLI 的工具非常有用，它们可能不想将文件保存到磁盘来存储输入类型。

解码器的默认输出是一个 JSON 对象，包含 `message` 字段中的解码消息和 `typedef` 字段中的解码所需 typedef。

输出格式与 CLI 编码器期望的输入格式匹配，使消息可以轻松编辑和重新编码。

或者，`-r`/`--raw-decode` 参数将提供更简单的输出，仅包含 JSON 消息而不含类型定义。如果你只想查看消息而不想编辑，或通过 `-ot`/`--output-type` 参数将类型定义保存到文件，此选项很有用。

`-it`/`--input-type` 和 `-ot`/`--output-type` 参数会让 CLI 从提供的文件读取和/或写入类型定义。

### 编码

`-e`/`--encode` 参数将 CLI 置于编码模式，接受 JSON 消息和类型定义，并输出编码后的 protobuf 消息到 stdout。

默认情况下，CLI 期望通过 stdin 传入一个 JSON 对象，其中包含 `message` 字段（消息的 JSON 表示）和 `typedef` 字段（类型定义）。此格式应与 CLI 解码器的输出格式匹配。

类型定义也可以通过 `-it`/`--input-type` 参数指定的文件提供。如果通过此参数提供了类型定义，且输入 JSON 中没有 `message` 字段，编码器将使用整个输入 JSON 作为消息（例如，带 `-r`/`--raw-decode` 的解码器输出）。

默认情况下，CLI 将编码后的 protobuf 字节输出到 stdout。

或者，`-j`/`--json-protobuf` 命令行标志将输出包含 `protobuf_data` 和 `typedef` 属性的 JSON payload。protobuf 数据字段将包含 base64 编码的 protobuf 数据。此格式与带 `-j`/`--json-protobuf` 属性的解码器期望的输入格式匹配。

### 编辑

消息和 typedef 可以按照与其他 Blackbox Protobuf 接口相同的规则轻松编辑。

来自解码器的 JSON 消息可以编辑以轻松更改字段值，然后再将 payload 传回编码器。如果类型定义中定义了字段类型，并且添加的值与该类型定义匹配，则可以添加字段。

如果你想编辑类型定义以更改字段名称或类型，请从输出 payload 或通过 `-ot`/`--output-typedef` 参数保存类型定义。编辑类型定义，然后使用 `-it`/`--input-typedef` 再次执行解码步骤。

不建议在将消息/typedef 传递给编码器之前直接编辑来自解码器的 typedef，因为这可能导致 payload 被错误编码。

### Payload 编码

Blackbox Protobuf 库尝试自动处理几种"包装器"编码。该库目前支持 gzip 压缩和 gRPC 头部。解码时，库会尝试检测这些包装器并解包 protobuf payload。如果识别出 payload 编码，它将存储在输出 JSON 的 `payload_encoding` 字段中。编码器在编码 payload 时会重新应用该包装器。

如果未提供 payload 编码，编码器将默认为 "none"（表示纯 protobuf）。对于其他编码选项，payload 编码设置为 "gzip" 或 "grpc"。

解码或编码时，可以通过 `-pe`/`--payload-encoding` 参数覆盖 payload 编码过程。

### Hex 转换

`convert` 子命令将十六进制字符串独立于 protobuf 转换为各种数据类型（整数、浮点数、字符串等）。适用于分析 TCP 二进制协议、网络转储或任何十六进制编码数据。

支持的 hex 输入格式：`01020304`、`01 02 03 04`、`01-02-03-04`、`0x01020304`。

支持的类型：

| 类型 | 描述 | 字节数 |
|------|------|--------|
| `int8` / `uint8` | 8-bit 整数 | 1 |
| `int16_le/be` / `uint16_le/be` | 16-bit 整数（小端/大端） | 2 |
| `int24_le/be` / `uint24_le/be` | 24-bit 整数（小端/大端） | 3 |
| `int32_le/be` / `uint32_le/be` | 32-bit 整数（小端/大端） | 4 |
| `int64_le/be` / `uint64_le/be` | 64-bit 整数（小端/大端） | 8 |
| `float_le/be` | 32-bit 浮点数 | 4 |
| `double_le/be` | 64-bit 浮点数 | 8 |
| `string` | UTF-8 字符串 | 可变 |
| `hex_raw` | 规范化的 hex 输出 | — |
| `bits` | 二进制表示 | — |

示例：

```bash
# 从参数传入单个 hex 字符串
bbpbcn convert -t int32_le 01020304

# Hex 字符串作为浮点数（小端）
bbpbcn convert -t float_le 0000803f

# Hex 字符串作为 UTF-8 字符串
bbpbcn convert -t string 48656c6c6f

# 大端变体
bbpbcn convert -t int32_be 01020304

# 从 stdin 管道输入 hex
echo "01020304" | bbpbcn convert -t int32_le

# 从 stdin 输入多个 hex 值（每行一个）
printf "01020304\n05060708" | bbpbcn convert -t int32_le

# JSON 输出
bbpbcn convert -t int32_le --json 01020304
echo "01020304" | bbpbcn convert -t int32_le --json
```

### 数据包分析

`analyze` 子命令并排分析多个十六进制数据包，自动检测头部字段结构：数据包长度、消息 ID、用户 ID 和 protobuf payload 边界。适用于在未知二进制格式的情况下逆向游戏协议（TCP、UDP、WebSocket）。

输入：来自同一协议会话的两个或多个十六进制数据包字符串。每个数据包会被逐字节解析和比较。分析器根据值范围和与数据包大小的相关性，为长度字段和 msgid 字段的字节偏移打分。

支持的 hex 输入格式：`01020304`、`01 02 03 04`、`01-02-03-04`、`0x01020304`。

选项：

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `-e le/be` | 字节序（小端/大端） | `le` |
| `--json` / `-j` | 输出为 JSON（机器可读） | 文本输出 |

示例：

```bash
# 使用小端字节序分析三个数据包
bbpbcn analyze -e le 0008000108D00F0110011801 0006000108960110011800 000A00020A047465737410021801

# 从 stdin 输入 hex 数据包（每行一个）
cat packets.txt | bbpbcn analyze -e le

# JSON 输出，便于脚本处理
bbpbcn analyze --json -e le 00080001 00060001

# 大端游戏协议
bbpbcn analyze -e be 000100020304 000200050607
```

### 消息对比

`diff` 子命令对比两个 protobuf 消息的字段差异，支持 hex 和 JSON 两种输入模式。适用于分析同一个操作在不同条件下的请求/响应差异。

```
bbpbcn diff <msg1_hex> <msg2_hex>                      # hex 模式（自动解码再对比）
bbpbcn diff --json-input <json1> <json2>                # JSON 模式（直接对比解析后的 dict）
bbpbcn diff <hex1> <hex2> -t typedef.json               # 指定 typedef 辅助解码
bbpbcn diff <hex1> <hex2> -j                            # JSON 格式输出差异结果
```

默认输出：
```
  字段差异:
    + level: 5
    - name: "alice"
    ~ score: 100 -> 200
```

选项：

| 选项 | 描述 |
|------|------|
| `-t` / `--typedef` | 用于解码的 typedef JSON 文件路径 |
| `--json-input` | 输入已经是解码后的 JSON 而非 hex |
| `-j` / `--json` | 以 JSON 格式输出差异结果 |

示例：

```bash
# 对比 hex 消息的字段差异
bbpbcn diff 08D00F10C401 08D00F10C801

# 对比已解码的 JSON 消息
bbpbcn diff --json-input '{"name":"alice"}' '{"name":"bob","level":1}'

# JSON 格式输出
bbpbcn diff 08D00F10C401 08D00F10C801 --json

# 使用 typedef 辅助解码后的对比
bbpbcn diff 08D00F10C401 08D00F10C801 -t ./saved_type.json
```

### .proto 文件导入/导出

`proto` 子命令在 bbpbcn typedef 格式与标准 `.proto` 文件之间转换，便于与其他 protobuf 工具链（protoc、protobuf-net 等）互通。

```
bbpbcn proto export -i <typedef.json> [-n <name>] [-p <package>]   # typedef → .proto
bbpbcn proto import -i <file.proto> [--save]                       # .proto → typedef
```

选项：

| 选项 | 描述 |
|------|------|
| `-i` / `--input` | 输入文件路径 |
| `-n` / `--name` | 消息名称（当 typedef 为裸字典时使用） |
| `-p` / `--package` | proto 包名 |
| `--save` | （import）直接保存到 known_types 配置，不输出到 stdout |

示例：

```bash
# 将 typedef 导出为 .proto
bbpbcn proto export -i typedef.json -n MyMessage
bbpbcn proto export -i typedef.json -n MyMessage -p my.package > message.proto

# 从 .proto 文件导入 typedef
bbpbcn proto import -i message.proto

# 导入并保存到 known_types
bbpbcn proto import -i message.proto --save
```

### 持久化数据库

`db` 子命令将分析结果持久化到 SQLite 数据库，支持有状态的渐进式分析流程。数据存储在 `$CWD/.bbpbcn/bbpb.db`，可通过 `BBPB_CN_DB_DIR` 环境变量覆盖存储目录。

```
bbpbcn db init                                             # 初始化数据库
bbpbcn db import <hex> -m <msgid> -p <project>             # 导入一条封包
bbpbcn db import-dir <dir> -m <msgid> -p <project>         # 批量导入目录中的 .hex 文件
bbpbcn db list [-p <project>] [--status <status>] [-l N]   # 列出消息
bbpbcn db get <id>                                         # 查看消息详情
bbpbcn db update <id> --<field> <value>                    # 更新字段
bbpbcn db delete <id>                                      # 删除消息
bbpbcn db search <keyword>                                 # 全文搜索
bbpbcn db stats [-p <project>]                             # 统计信息
bbpbcn db export [-p <project>] [-f proto|json]            # 导出 typedef
bbpbcn db history <id>                                     # typedef 变更历史
bbpbcn db session create -p <project> -n <name>            # 创建分析会话
bbpbcn db session list                                     # 列出会话
bbpbcn db session get <id>                                 # 查看会话详情
bbpbcn db session delete <id>                              # 删除会话
```

可用字段（import / update）：

| 字段 | 说明 |
|------|------|
| `-m` / `--msgid` | 消息 ID |
| `-p` / `--project` | 项目/游戏名 |
| `-d` / `--direction` | 方向（如 C2S / S2C） |
| `-D` / `--describe` | 功能描述 |
| `-r` / `--remark` | 备注 |
| `--status` | 状态（pending / analyzing / confirmed） |
| `--hex` | hex payload |
| `--typedef` | typedef JSON 文件路径 |

数据库表结构：

- `messages` — 主表：project, msgid, direction, hex, typedef, describe, remark, status, 时间戳
- `typedef_history` — typedef 变更记录（每次更新自动保存快照 + 版本号）
- `sessions` — 分析会话：project, name, msg_ids, notes

示例：

```bash
# 初始化
bbpbcn db init

# 导入批包
bbpbcn db import 08D00F10C401 -m 1001 -p "game_x" -d "C2S" -D "心跳包"
bbpbcn db import 08D00F10C801 -m 1002 -p "game_x" -d "C2S" -D "登录请求"

# 查看列表
bbpbcn db list -p game_x
bbpbcn db list --status pending

# 查看详情
bbpbcn db get 1
bbpbcn db get 1 --json

# 更新 typedef 和状态（auto-saved to history）
bbpbcn db update 1 --typedef ./refined.json --status confirmed
bbpbcn db update 1 --remark "已确认是心跳"

# 搜索
bbpbcn db search 心跳
bbpbcn db search 1001

# 统计
bbpbcn db stats -p game_x

# 导出整个项目为 .proto
bbpbcn db export -p game_x -f proto

# 查看 typedef 版本历史
bbpbcn db history 1

# 创建分析会话
bbpbcn db session create -p game_x -n "第一轮分析" -m "1,2"

# 批量导入 hex 文件目录
bbpbcn db import-dir ./captures/ -m 2001 -p game_x
```
