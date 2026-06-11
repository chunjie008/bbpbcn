# bbpb-cn

> **Forked from [blackboxprotobuf](https://github.com/nccgroup/blackboxprotobuf). 中文注释 + 增强类型推测能力。**

PyPi 包名：`bbpb-cn`，Python 导入名：`bbpb_cn`。

## 描述

bbpb-cn 是 blackboxprotobuf 的中文 fork 版本，用于处理编码后的 Protocol Buffers（protobuf）数据，无需匹配的 .proto 文件。在保留上游所有功能的基础上，增强了对嵌套消息的类型推测、VARINT/Fixed 类型后验推断等能力。

Protobuf 是 Google 推出的一种二进制序列化格式，可作为 JSON 或 XML 等格式的更高效替代方案。开发者可以在 `.proto` 文件中定义消息格式，并使用 protobuf 编译器生成所选语言的 message 处理代码。protobuf 编码是二进制的，不像 json/xml 那样可读或易于手动修改。该格式利用通信双方都拥有消息定义这一前提，省去了大量类型信息。这在提高效率的同时，也增加了分析或修改网络流量的难度。

bbpb-cn 旨在在没有消息定义的情况下处理 protocol buffers。它 fork 自 NCC Group 的 blackboxprotobuf，增强了类型推测能力并提供了完整的中文注释。

## 工具

本仓库包含多个用于处理 protocol buffers 的接口：

- 一个 jython burp 扩展，位于 [burp/](https://github.com/chunjie008/bbpb_cn/tree/master/burp)
- 一个可被其他应用使用的 Python 库，位于 [lib/](https://github.com/chunjie008/bbpb_cn/tree/master/lib)
- 一个基于 Python 的 CLI，嵌入在[库](https://github.com/chunjie008/bbpb_cn/tree/master/lib/CLI.md)中
- 一个 mitmproxy 插件，位于 [mitmproxy](https://github.com/chunjie008/bbpb_cn/tree/master/mitmproxy)

## 文档

除了每个工具的 `README.md` 之外，还有以下文档：

- [类型定义指南](docs/TypeDefs.md) — 编辑 typedef 以修复类型和提升可读性的指南

## 未来工具

未来可能基于 bbpb_cn 构建的一些工具：

- protobuf 类型发现工具
