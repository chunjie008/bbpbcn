# Blackbox Protobuf

**Blackbox Protobuf 现在在 PyPi 上有官方包，名称为 `bbpb`。`blackboxprotobuf` 包是较旧的分支。**

## 描述

Blackbox Protobuf 是一套用于处理编码后的 Protocol Buffers（protobuf）的工具，无需匹配的 protobuf 定义文件。

Protobuf 是 Google 推出的一种二进制序列化格式，可作为 JSON 或 XML 等格式的更高效替代方案。开发者可以在 `.proto` 文件中定义消息格式，并使用 protobuf 编译器生成所选语言的 message 处理代码。protobuf 编码是二进制的，不像 json/xml 那样可读或易于手动修改。该格式利用通信双方都拥有消息定义这一前提，省去了大量类型信息。这在提高效率的同时，也增加了分析或修改网络流量的难度。

Blackbox Protobuf 旨在允许在没有消息定义的情况下处理 protocol buffers。它最初是作为一个 Burp 扩展实现的，用于在移动端渗透测试中解码和修改消息，后来也被用于逆向工程和取证工具。

## 工具

本仓库包含多个用于处理 protocol buffers 的接口：

- 一个 jython burp 扩展，位于 [burp/](https://github.com/nccgroup/blackboxprotobuf/tree/master/burp)
- 一个可被其他应用使用的 Python 库，位于 [lib/](https://github.com/nccgroup/blackboxprotobuf/tree/master/lib)
- 一个基于 Python 的 CLI，嵌入在[库](https://github.com/nccgroup/blackboxprotobuf/tree/master/lib/CLI.md)中
- 一个 mitmproxy 插件，位于 [mitmproxy](https://github.com/nccgroup/blackboxprotobuf/tree/master/mitmproxy)

## 文档

除了每个工具的 `README.md` 之外，还有以下文档：

- [类型定义指南](docs/TypeDefs.md) — 编辑 typedef 以修复类型和提升可读性的指南

## 未来工具

未来可能基于 blackboxprotobuf 构建的一些工具：

- protobuf 类型发现工具
