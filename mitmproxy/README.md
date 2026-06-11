# Blackbox Protobuf Mitmproxy 插件

## 描述

本目录包含一个 mitmproxy (<https://mitmproxy.org/>) 的插件，使用 Blackbox Protobuf 库来解码和编辑代理的 protobuf 消息。

## 安装

1. 克隆 bbpbcn 仓库：
   
   ```
   git clone https://github.com/chunjie008/bbpbcn.git
   ```
   
2. 更新包含依赖的子模块：
   
   ```
   cd bbpbcn/
   git submodule update --init
   ```

3. 使用该插件运行 mitmproxy：
   
   ```
   mitmproxy -s mitmproxy/bbpbcn.py
   ```

### 替代安装方法

1. 在与 `mitmproxy` 相同的环境中安装 `bbpbcn` Python 包。
   
   ```
   pip install bbpbcn
   ```
   
   如果 `mitmproxy` 安装在虚拟环境中，则 `bbpbcn` 包也需要安装在该虚拟环境中。

2. 从 <https://github.com/chunjie008/bbpbcn/blob/master/mitmproxy/bbpbcn.py> 下载 `bbpbcn.py`。

3. 使用该插件脚本运行 mitmproxy：
   
   ```
   mitmproxy -s mitmproxy/bbpbcn.py
   ```

## 用法

### 被动解码

Blackbox Protobuf 插件提供了一个内容视图，可以自动解码 mitmproxy 中显示的 protobuf、gRPC 消息和 websocket。该内容视图在可用时会使用已保存的类型（例如，为字段命名或更改类型），否则默认进行匿名解码。

内容视图在 mitmweb 中也能工作，但编辑消息和类型的命令不可用。

### 持久化类型数据

插件会记住已编辑的类型和关联的端点，但如果 mitmproxy 关闭或插件重新加载，这些数据将丢失。

mitmproxy 配置中的 `bbpbcn_project_file` 选项将使插件从提供的文件加载类型，然后自动将任何更改写回文件。如果你有大量配置，建议定期备份项目文件以确保数据不被覆盖。

类型也可以使用 `:bbpbcn.project.save` 和 `:bbpbcn.project.load` 命令手动保存或加载。

### 命令

消息和类型编辑功能通过 mitmproxy 命令提供。

命令操作当前选中的 flow。大多数命令接受一个 `flow_part` 参数，指示所需的 protobuf payload 在消息中的位置。当前支持的 flow 部分有：

* `request-body` — 请求体
* `response-body` — 响应体
* `websocket`（用于 `bbpbcn.edit`，`bbpbcn.edit_type` 不支持）
* `websocket-request`（用于 `bbpbcn.edit_type`，`bbpbcn.edit` 不支持）
* `websocket-response`（用于 `bbpbcn.edit_type`，`bbpbcn.edit` 不支持）

命令参数支持 tab 补全。

#### `:bbpbcn.edit`

`:bbpbcn.edit` 命令将打开一个文本编辑器，显示解码为 JSON 的 protobuf，类似于在 mitmproxy 中编辑其他 HTTP 消息。编辑后的 JSON payload 将被重新编码为 protobuf，以便重放或恢复。

`request-body` 和 `response-body` flow 部分将编辑 HTTP body 中的 protobuf 消息。`websocket` flow 部分将编辑 websocket flow 中的最后一条消息。

该插件目前不支持 HTTP 消息其他位置的 protobuf payload，但你可以根据特定用例自定义插件。

#### `:bbpbcn.edit_type`

`:bbpbcn.edit_type` 命令将打开一个文本编辑器，编辑用于 protobuf 数据的类型定义。这可用于添加字段名称或更改字段类型。

如果端点分配了命名类型，则编辑的是该命名类型，更改将应用于使用相同命名类型的所有其他端点。如果类型未命名，则编辑后的类型定义仅对该端点生效。

#### `:bbpbcn.new_type`

`:bbpbcn.new_type` 命令将为当前类型附加一个名称，并将其存储在 `known_types` 中。命名类型随后可以应用于多个端点，你可以在命名类型之间随意切换，而不会丢失类型定义。

#### `:bbpbcn.apply_type`

`:bbpbcn.apply_type` 命令会将先前保存的命名类型应用于端点/protobuf payload。应用 `(clear)` 类型名称将移除该端点的已保存类型，使解码重置。

警告：如果当前端点有一个未命名的已编辑类型，应用命名类型时该编辑后的类型定义将丢失。

如果当前端点关联了另一个命名类型，该命名类型将安全保存，以后可以重新应用。

#### `:bbpbcn.del_type`

`:bbpbcn.del_type` 命令用于删除命名类型。与该命名类型关联的所有端点也将被重置。

#### `:bbpbcn.project.save` 和 `:bbpbcn.project.load`

这些命令将手动保存/加载一个一次性的 Blackbox Protobuf 项目 JSON 文件。该文件包含所有编辑过的类型定义以及所有端点到类型定义的映射。

## gRPC 说明

该插件已使用 Python gRPC 客户端测试过，能够默认拦截消息。然而，过去 mitmproxy 在拦截某些应用的 gRPC 连接时曾遇到过问题，会将连接注册为 PRI 方法，或无法拦截请求。

问题似乎在于某些 gRPC 实现使用独特的 `grpc-exp` ALPN 值，代理不知道该值如何处理。过去有效的一种解决方法是克隆 mitmproxy 并修改检查 `h2` 的条件，使其也适用于 `grpc-exp`。

另一个可能的解决方案是 <https://github.com/mitmproxy/mitmproxy/issues/3052#issuecomment-1676020354> 中描述的插件修改，但尚未经过 Blackbox Protobuf 插件的测试。
