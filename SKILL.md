# Skill: bbpbcn

# bbpbcn — blackboxprotobuf 增强版 CLI/SDK

> Forked from [blackboxprotobuf](https://github.com/nccgroup/blackboxprotobuf)，增强类型推测（嵌套消息、VARINT/Fixed 后验推断），中文注释。
> 项目仓库：https://github.com/chunjie008/bbpbcn

## 安装

```bash
pip install --user bbpb     # 已全局安装
```

或从项目 `lib/` 目录源码安装：`pip install .`

依赖仅 `six`，纯 Python，无 C 扩展。

## CLI 参数

| 参数 | 说明 |
|------|------|
| `-e, --encode` | 编码模式（默认解码） |
| `-j, --json-protobuf` | JSON 格式输入/输出（含 base64 protobuf_data/typedef） |
| `--compact` | 紧凑 JSON 输出 |
| `-pe, --payload-encoding` | 指定包装编码（gzip、grpc） |
| `-it, --input-type <file>` | 从文件读 typedef |
| `-ot, --output-type <file>` | 将 typedef 写入文件 |
| `-r, --raw-decode` | 只输出 message JSON，不输出 typedef |

## 常用操作

### 解码原始 protobuf 二进制
```bash
bbpbcn < message.bin                              # 完整输出（message + typedef）
bbpbcn -r < message.bin                           # 仅 message
bbpbcn -it typedef.json < message.bin             # 带已知 typedef 解码
```

### 编码为 protobuf 二进制
```bash
bbpbcn -e < message.json > encoded.bin
```

### JSON protobuf 模式（输入含 base64）
```bash
echo '{"protobuf_data": "CJIBEgd0ZXN0aW5n"}' | bbpbcn -j
```

### 处理包装编码
```bash
bbpbcn -pe gzip < compressed.bin
bbpbcn -pe grpc < grpc_wrapped.bin
```

## 子命令

> **无子命令时**（即直接调用 `bbpbcn`）执行核心 **解码/编码**，见上方「常用操作」。

### convert — Hex 转换

支持的 hex 输入格式：`01020304`、`01 02 03 04`、`01-02-03-04`、`0x01020304`。

```bash
bbpbcn convert -t int32_le 01020304               # hex → 67305985
bbpbcn convert -t string 48656c6c6f               # hex → "Hello"
bbpbcn convert -t float_le 0000803f               # hex → 1.0
bbpbcn convert -t int32_be 01020304               # 大端
bbpbcn convert -t int32_le --json 01020304        # JSON 格式输出
echo "01020304" | bbpbcn convert -t int32_le      # 从 stdin 输入
printf "01020304\n05060708" | bbpbcn convert -t int32_le   # 多行 stdin
```

支持类型：

| 类型 | 字节数 |
|------|--------|
| `int8` / `uint8` | 1 |
| `int16_le/be` / `uint16_le/be` | 2 |
| `int24_le/be` / `uint24_le/be` | 3 |
| `int32_le/be` / `uint32_le/be` | 4 |
| `int64_le/be` / `uint64_le/be` | 8 |
| `float_le/be` | 4 |
| `double_le/be` | 8 |
| `string` | 可变 |
| `hex_raw` | — |
| `bits` | — |

### analyze — 数据包分析

```bash
bbpbcn analyze -e le <hex1> <hex2> [...]                    # 分析多个数据包
bbpbcn analyze --json -e le 00080001 00060001               # JSON 输出
cat packets.txt | bbpbcn analyze -e le                       # 从 stdin 输入
```

自动检测：**长度字段、消息 ID、用户 ID、protobuf payload 边界**，适用于逆向未知 TCP/UDP/WebSocket 二进制协议。

选项：
| 选项 | 描述 | 默认值 |
|------|------|--------|
| `-e le/be` | 字节序（小端/大端） | `le` |
| `-j` / `--json` | JSON 格式输出 | 文本输出 |

### diff — 消息对比

```bash
bbpbcn diff <hex1> <hex2>                                   # hex 模式（自动解码再对比）
bbpbcn diff --json-input '{"name":"alice"}' '{"name":"bob","level":1}'  # JSON 直接对比
bbpbcn diff <hex1> <hex2> -t typedef.json                   # 指定 typedef 辅助解码
bbpbcn diff <hex1> <hex2> -j                                # JSON 格式输出差异
```

默认输出格式：
```
  字段差异:
    + level: 5
    - name: "alice"
    ~ score: 100 -> 200
```

选项：
| 选项 | 描述 |
|------|------|
| `-t` / `--typedef` | typedef JSON 文件路径 |
| `--json-input` | 输入已经是解码后的 JSON |
| `-j` / `--json` | JSON 格式输出差异 |

### proto — .proto 文件导入/导出

```bash
bbpbcn proto export -i typedef.json -n MyMessage            # typedef → .proto
bbpbcn proto export -i typedef.json -n Msg -p my.package    # 指定包名（可选）
bbpbcn proto import -i message.proto                        # .proto → typedef
bbpbcn proto import -i message.proto --save                  # 导入并保存到 known_types
```

选项：
| 选项 | 描述 |
|------|------|
| `-i` / `--input` | 输入文件路径 |
| `-n` / `--name` | 消息名称（裸字典时必需） |
| `-p` / `--package` | proto 包名 |
| `--save` | （import）直接保存到配置，不输出 stdout |

### db — 持久化数据库（SQLite）


```bash
bbpbcn db init                                      # 初始化数据库（创建表）
bbpbcn db import <hex> -m <msgid> -p <project>      # 导入一条封包
bbpbcn db import-dir <dir> -m <msgid> -p <project>  # 批量导入目录中的 .hex 文件
bbpbcn db list [-p project] [--status status] [-l N] # 列出消息
bbpbcn db get <id>                                  # 查看消息详情
bbpbcn db update <id> --<field> <value>             # 更新字段
bbpbcn db delete <id>                               # 删除消息
bbpbcn db search <keyword>                          # 全文搜索（支持 project 限定）
bbpbcn db stats [-p project]                        # 统计信息
bbpbcn db export [-p project] [-f proto|json]       # 导出 typedef
bbpbcn db history <id>                              # typedef 变更历史（自动版本快照）
bbpbcn db session create -p <project> -n <name>     # 创建分析会话
bbpbcn db session list [-p project]                 # 列出会话
bbpbcn db session get <id>                          # 查看会话详情
bbpbcn db session delete <id>                       # 删除会话
```

可用字段（import / update）：

| 参数 | 说明 |
|------|------|
| `-m` / `--msgid` | 消息 ID |
| `-p` / `--project` | 项目/游戏名 |
| `-d` / `--direction` | 方向（C2S / S2C） |
| `-D` / `--describe` | 功能描述 |
| `-r` / `--remark` | 备注 |
| `--status` | 状态（pending / analyzing / confirmed） |
| `--hex` | hex payload |
| `--typedef` | typedef JSON 文件路径 |

数据存储于 `$CWD/.bbpbcn/bbpb.db`，可通过 `BBPB_CN_DB_DIR` 环境变量覆盖目录。

## 典型工作流

```bash
# 1. 拦截二进制 protobuf → 解码
bbpbcn -r < captured.bin > decoded.json
# 2. 编辑 decoded.json
# 3. 重新编码
bbpbcn -e < decoded.json > tampered.bin
# 4. 重放
```

## Python API

```python
from bbpbcn import (
    decode_message,       # protobuf 二进制 → (message_dict, typedef)
    encode_message,       # (message_dict, typedef) → protobuf 二进制
    protobuf_to_json,     # protobuf 二进制 → (json_str, typedef)
    protobuf_from_json,   # (json_str, typedef) → protobuf 二进制
    validate_typedef,     # 校验 typedef 格式
    import_protofile,     # .proto 文件 → typedef dict
    export_protofile,     # typedef dict → .proto 文件
    sort_typedef,         # typedef 字段按编号排序
)

# 解码
message, typedef = decode_message(b'\x08\x96\x01...')

# 编码
encoded = encode_message(message, typedef)
```

## 注意事项

- 默认从 **stdin 读二进制**（解码）或 **JSON 文本**（编码）
- `bytes` 字段在 JSON 中用 **Latin-1** 编码显示以保留原始字节（因 JSON 不支持原始 bytes，Latin-1 是单字节无损映射）。解码后如需操作 bytes 值，应用 `value.encode('latin-1')` 还原
- 仅依赖 `six`，纯 Python，兼容 Python 3.8+
- typedef 是 blackboxprotobuf 自有格式（JSON 字典），非标准 .proto 文件
