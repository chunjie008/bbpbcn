# 版权所有 (c) 2018-2023 NCC Group Plc
#
# 特此免费授予任何获得本软件及相关文档文件（“软件”）副本的人，不受限制地处理
# 本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或
# 销售本软件副本的权利，并允许获得本软件的人这样做，但须符合以下条件：
#
# 上述版权声明和本许可声明应包含在本软件的所有副本或实质性部分中。
#
# 本软件按“原样”提供，不作任何明示或暗示的担保，包括但不限于对适销性、特定
# 用途适用性和非侵权的担保。在任何情况下，作者或版权持有人均不对因使用本软件
# 而产生的任何索赔、损害或其他责任承担责任，无论是合同行为、侵权行为还是其他
# 行为。

import inspect
import os
import sys
import logging


try:
    import bbpbcn
except ModuleNotFoundError:
    # 两个 abspath 是因为 dirname 如果只运行 bbpbcn.py 会返回空字符串
    _BASE_DIR = os.path.abspath(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        + "/.."
    )
    sys.path.insert(0, _BASE_DIR + "/lib/")
    sys.path.insert(0, _BASE_DIR + "/mitmproxy/")
    sys.path.insert(0, _BASE_DIR + "/mitmproxy/deps/six/")
    import bbpbcn

from bbpbcn.lib import payloads
from bbpbcn.lib.exceptions import bbpbcnException

import json
from collections.abc import Sequence

from typing import TypeVar, Callable, Optional

from mitmproxy import (
    command,
    contentviews,
    ctx,
    http,
    flow,
    types,
    exceptions,
    websocket,
)
from mitmproxy.tools.console import overlay, signals, keymap


class bbpbcnAddon:
    def __init__(self):
        self.view = bbpbcnView(self)

        self.bbpbcn_config = bbpbcn.lib.config.Config()
        self.typedef_lookup = {}
        self.project_file = None

    def load(self, loader):
        contentviews.add(self.view)

        loader.add_option(
            "bbpbcn_project_file",
            typespec=str,
            default="",
            help="将 known_types 和 typedef 映射持久化到项目文件。文件会自动写入，因此建议定期备份",
        )

    def _load_project_file(self, project_file: str | None = None):
        self.project_file = ctx.options.bbpbcn_project_file

        if not project_file and not self.project_file:
            return

        if not project_file:
            project_file = self.project_file

        if not self.project_file:
            return

        logging.info("正在从文件加载项目数据")
        try:
            with open(project_file, "r") as f:
                project_data = json.load(f)

            # 以防我们有现有数据，更新已有的 typedef_lookup 和 bbpbcn_config
            self.typedef_lookup.update(project_data["typedef_lookup"])
            self.bbpbcn_config.known_types.update(project_data["known_types"])
        except FileNotFoundError:
            # 我们还没有写入任何内容，所以文件可能还不存在
            pass
        self._refresh_view()

    def _save_project_file(self, project_file: str | None = None):
        if not project_file and not self.project_file:
            return

        if not project_file:
            project_file = self.project_file

        logging.info("正在将项目数据写入文件")
        data = {
            "typedef_lookup": self.typedef_lookup,
            "known_types": self.bbpbcn_config.known_types,
        }
        with open(project_file, "w") as f:
            json.dump(data, f, indent=2)

    def configure(self, updates: set[str]):
        if "bbpbcn_project_file" in updates:
            self._load_project_file()
            self._save_project_file()

    def done(self):
        contentviews.remove(self.view)

    @command.command("bbpbcn.edit")
    @command.argument("flow_part", type=types.Choice("bbpbcn.options.edit_part"))
    def bbpbcn_edit(self, flow_part: str) -> None:
        flow = ctx.master.view.focus.flow

        if flow_part == "request-body":
            message = flow.request
        elif flow_part == "response-body":
            if not flow.response:
                raise exceptions.CommandError(
                    f"流程部分为 response-body，但流程没有响应"
                )
            message = flow.response
        elif flow_part == "websocket":
            # 编辑最后一个 websocket 消息
            message = flow.websocket.messages[-1]
        else:
            raise exceptions.CommandError(f"未知的 flow_part: {flow_part}")

        message_hash = _message_hash(message.content, message, flow)

        typedef = self.typedef_lookup.get(message_hash)
        message_json, typedef_out, encoding_alg = _decode_protobuf(
            message.content, typedef, self.bbpbcn_config
        )

        def message_callback(edited_json: str) -> None:
            protobuf_data = bbpbcn.protobuf_from_json(
                edited_json, typedef_out
            )
            data = payloads.encode_payload(protobuf_data, encoding_alg)
            message.content = bytes(data)
            self._refresh_view()

        _spawn_validating_editor(message_json, message_callback)

    @command.command("bbpbcn.edit_type")
    @command.argument("flow_part", type=types.Choice("bbpbcn.options.edit_type_part"))
    def bbpbcn_edit_type(self, flow_part: str) -> None:
        flow = ctx.master.view.focus.flow

        typedef, message_hash = self._resolve_type(flow_part)

        typedef_json = json.dumps(typedef, indent=2)

        def typedef_callback(typedef_json: str) -> None:
            new_typedef = json.loads(typedef_json)
            bbpbcn.validate_typedef(
                new_typedef, typedef
            )  # 根据旧 typedef 验证新 typedef

            bbpbcn.lib.api._strip_typedef_annotations(new_typedef)
            known_type = self.typedef_lookup.get(message_hash)
            if isinstance(known_type, str):
                # 这是一个命名 typedef，编辑已知的 typedef 而不是保存的值
                self.bbpbcn_config.known_types[known_type] = new_typedef
                self._save_project_file()
            else:
                # 信任 validate_typedef，不尝试再次使用 typedef 解码或重新编码
                self.typedef_lookup[message_hash] = new_typedef
                self._save_project_file()

            self._refresh_view()

        _spawn_validating_editor(typedef_json, typedef_callback)

    @command.command("bbpbcn.apply_type")
    @command.argument("flow_part", type=types.Choice("bbpbcn.options.edit_type_part"))
    @command.argument("typename", type=types.Choice("bbpbcn.options.known_types"))
    def bbpbcn_apply_type(self, flow_part: str, typename: str) -> None:
        flow = ctx.master.view.focus.flow
        if typename not in self.bbpbcn_config.known_types and typename != "(clear)":
            raise exceptions.CommandError(f"类型 {typename} 不是已知类型")
        flow = ctx.master.view.focus.flow
        if not flow:
            raise exceptions.CommandError("未选择流程。")
        if flow_part.startswith("request") or flow_part.startswith("response"):
            if flow_part == "request-body":
                message = flow.request
            elif flow_part == "response-body":
                if not flow.response:
                    raise exceptions.CommandError(
                        f"流程部分为 response-body，但流程没有响应"
                    )
                message = flow.response
            message_hash = _message_hash(message.content, message, flow)
            if typename == "(clear)":
                logging.info("弹出消息 hash")
                self.typedef_lookup.pop(message_hash, None)
                self._save_project_file()
                self._refresh_view()
                return

            # 验证我们是否可以使用新类型解码该消息
            try:
                _decode_protobuf(
                    message.content, typename, self.bbpbcn_config, fallback=False
                )
            except bbpbcnException as ex:
                raise exceptions.CommandError(
                    f"将类型名称 {typename} 应用于部分 {flow_part} 时出错: {ex}"
                )

        elif flow_part.startswith("websocket"):
            # WebSocket 没有单一的 typedef 可编辑
            # 相反，我们将基于所有消息构建一个 typedef
            if flow_part == "websocket-request":
                if not flow.websocket:
                    raise exceptions.CommandError(
                        f"流程部分为 websocket-request，但流程不是 websocket"
                    )
                messages = [
                    message
                    for message in flow.websocket.messages
                    if message.from_client
                ]
            elif flow_part == "websocket-response":
                if not flow.websocket:
                    raise exceptions.CommandError(
                        f"流程部分为 websocket-response，但流程不是 websocket"
                    )
                messages = [
                    message
                    for message in flow.websocket.messages
                    if not message.from_client
                ]
            if not messages:
                raise exceptions.CommandError(
                    f"未找到流程部分 {flow_part} 的任何消息"
                )
            message_hash = _message_hash(messages[0].content, messages[0], flow)
            if typename == "(clear)":
                logging.info("弹出消息 hash")
                self.typedef_lookup.pop(message_hash, None)
                self._save_project_file()
                self._refresh_view()
                return
            # 验证我们是否可以使用该类型解码所有消息
            for message in messages:
                try:
                    _decode_protobuf(
                        message.content, typename, self.bbpbcn_config, fallback=False
                    )
                except bbpbcnException as ex:
                    raise exceptions.CommandError(
                        f"将类型名称 {typename} 应用于部分 {flow_part} 时出错: {ex}"
                    )
        # 成功
        self.typedef_lookup[message_hash] = typename
        self._save_project_file()
        self._refresh_view()

    @command.command("bbpbcn.new_type")
    @command.argument("flow_part", type=types.Choice("bbpbcn.options.edit_type_part"))
    @command.argument("typename", type=str)
    def bbpbcn_new_type(self, flow_part: str, typename: str) -> None:
        if typename == "(clear)":
            raise exceptions.CommandError(f"错误：类型名称 {typename} 无效。")
        typedef, message_hash = self._resolve_type(flow_part)

        bbpbcn.lib.api._strip_typedef_annotations(typedef)
        self.typedef_lookup[message_hash] = typename
        self.bbpbcn_config.known_types[typename] = typedef
        self._save_project_file()

        self._refresh_view()

    def _resolve_type(self, flow_part):
        flow = ctx.master.view.focus.flow
        if not flow:
            raise exceptions.CommandError("未选择流程。")
        if flow_part.startswith("request") or flow_part.startswith("response"):
            if flow_part == "request-body":
                message = flow.request
            elif flow_part == "response-body":
                if not flow.response:
                    raise exceptions.CommandError(
                        f"流程部分为 response-body，但流程没有响应"
                    )
                message = flow.response
            message_hash = _message_hash(message.content, message, flow)
            saved_typedef = self.typedef_lookup.get(message_hash)
            message_json, typedef, encoding_alg = _decode_protobuf(
                message.content, saved_typedef, self.bbpbcn_config
            )
        elif flow_part.startswith("websocket"):
            # WebSocket 没有单一的 typedef 可编辑
            # 相反，我们将基于所有消息构建一个 typedef
            if flow_part == "websocket-request":
                if not flow.websocket:
                    raise exceptions.CommandError(
                        f"流程部分为 websocket-request，但流程不是 websocket"
                    )
                messages = [
                    message
                    for message in flow.websocket.messages
                    if message.from_client
                ]
            elif flow_part == "websocket-response":
                if not flow.websocket:
                    raise exceptions.CommandError(
                        f"流程部分为 websocket-response，但流程不是 websocket"
                    )
                messages = [
                    message
                    for message in flow.websocket.messages
                    if not message.from_client
                ]
            if not messages:
                raise exceptions.CommandError(
                    f"未找到流程部分 {flow_part} 的任何消息"
                )
            message_hash = _message_hash(messages[0].content, messages[0], flow)
            saved_typedef = self.typedef_lookup.get(message_hash)
            try:
                typedef = saved_typedef
                message_jsons = []
                for message in messages:
                    message_json, typedef, encoding_alg = _decode_protobuf(
                        message.content, typedef, self.bbpbcn_config, fallback=False
                    )
                    message_jsons.append(message_json)
            except bbpbcnException:
                typedef = {}
                message_jsons = []
                for message in messages:
                    message_json, typedef, encoding_alg = _decode_protobuf(
                        message.content, typedef, self.bbpbcn_config, fallback=False
                    )
                    message_jsons.append(message_json)
        else:
            raise exceptions.CommandError(f"未知的 flow_part: {flow_part}")

        return typedef, message_hash

    @command.command("bbpbcn.del_type")
    @command.argument("typename", type=types.Choice("bbpbcn.options.known_types"))
    def bbpbcn_del_type(self, typename: str) -> None:
        if typename not in self.bbpbcn_config.known_types:
            raise exceptions.CommandError(f"错误：类型 {typename} 未知")
        self.bbpbcn_config.known_types.pop(typename, None)
        keys_to_remove = [
            key for key, value in self.typedef_lookup.items() if value == typename
        ]
        for key in keys_to_remove:
            self.typedef_lookup.pop(key, None)
        self._save_project_file()
        self._refresh_view()

    @command.command("bbpbcn.options.edit_part")
    def bbpbcn_options_edit_part(self) -> Sequence[str]:
        flow = ctx.master.view.focus.flow
        if not flow:
            raise exceptions.CommandError("未选择流程。")

        # 提示用户选择要编辑的部分
        if flow.websocket:
            if len(flow.websocket.messages) > 0:
                return ["websocket"]
            else:
                return []
        elif flow.response:
            return [
                "request-body",
                "response-body",
            ]
        else:
            return ["request-body"]

    @command.command("bbpbcn.options.edit_type_part")
    def bbpbcn_options_edit_type_part(self) -> Sequence[str]:
        flow = ctx.master.view.focus.flow
        if flow.websocket:
            return ["websocket-request", "websocket-response"]
        if flow.response:
            return [
                "request-body",
                "response-body",
            ]
        return ["request-body"]

    @command.command("bbpbcn.options.known_types")
    def bbpbcn_options_known_types(self) -> Sequence[str]:
        typenames = list(self.bbpbcn_config.known_types.keys())
        return typenames + ["(clear)"]

    def _refresh_view(self):
        ctx.master.window.stacks[0].windows["flowview"].body.contentview_changed(None)

    @command.command("bbpbcn.project.load")
    def bbpbcn_project_load(self, project_file: str) -> None:
        # TODO 若有错误能传播到这里就好了
        self._load_project_file(project_file)

    @command.command("bbpbcn.project.save")
    def bbpbcn_project_save(self, project_file: str) -> None:
        # TODO 若有错误能传播到这里就好了
        self._save_project_file(project_file)


class bbpbcnView(contentviews.View):
    name = "Blackbox Protobuf"

    def __init__(self, addon: bbpbcnAddon):
        self.addon = addon

    def __call__(
        self,
        data: bytes,
        *,
        content_type: str | None = None,
        flow: flow.Flow | None = None,
        http_message: http.Message | None = None,
        **unknown_metadata,
    ) -> contentviews.TViewResult:
        # 不支持 TCP 或 UDP 流程
        if not isinstance(flow, http.HTTPFlow):
            return None

        if len(data) == 0:
            return

        # message_hash 用于根据 URL 和消息类型查找此请求的适当 typedef
        message_hash = _message_hash(data, http_message, flow)

        typedef = self.addon.typedef_lookup.get(message_hash)

        message, typedef_out, encoding_alg = _decode_protobuf(
            data, typedef, self.addon.bbpbcn_config
        )

        title = "Protobuf"
        if isinstance(typedef, str):
            title += f"  |  类型: {typedef}"
        else:
            title += f"  |  类型: 匿名"

        return title, contentviews.format_text(message)

    def render_priority(
        self,
        data: bytes,
        *,
        content_type: str | None = None,
        flow: flow.Flow | None = None,
        http_message: http.Message | None = None,
        **unknown_metadata,
    ) -> float:
        if content_type:
            if "protobuf" in content_type or "grpc" in content_type:
                return 2
            else:
                return 0
        # 我们不知道是否能解码 protobuf，所以选择
        # 适用于所有 websocket
        if flow.websocket:
            return 1
        return 0


# 对于某些情况，可以通过是否来自客户端来判断 is_request，但这可以改进
def _message_hash(
    data: bytes,
    message: http.Message | websocket.WebSocketMessage | None,
    flow: flow.Flow | None,
):
    if isinstance(message, http.Request):
        return f"request|{flow.request.url}"
    elif isinstance(message, http.Response):
        return f"response|{flow.request.url}"
    elif flow.websocket:
        if message is None or not isinstance(message, websocket.WebSocketMessage):
            # TODO 这非常 hacky，如果有大量消息可能会浪费计算资源
            # Mitmproxy 不会为内容视图提供 WebSocketMessage 消息类型，
            # 所以我们无法仅从消息判断其方向。
            try:
                message = next(
                    (m for m in flow.websocket.messages if m.content == data)
                )
            except StopIteration:
                logging.warn(
                    "消息哈希在 flow.websocket.messages 中找不到匹配的消息"
                )
                message = None

        # 如果我们始终无法确定消息，默认为请求
        if message and not message.from_client:
            return f"websocket-response|{flow.request.url}"
        else:
            return f"websocket-request|{flow.request.url}"
    else:
        logging.warn(
            f"bbpbcn 内容视图收到了既不是 websocket、请求也不是响应的视图: {type(http_message)}"
        )
        return None


def _decode_protobuf(data, typedef, config, fallback=True):
    try:
        decoders = payloads.find_decoders(data)
        for decoder in decoders:
            try:
                protobuf_data, encoding_alg = decoder(data)
            except bbpbcnException:
                continue

            try:
                message, typedef_out = bbpbcn.lib.protobuf_to_json(
                    protobuf_data, typedef, config=config
                )

                return message, typedef_out, encoding_alg
            except bbpbcnException as exc:
                if encoding_alg == "none":
                    raise exc
                continue
    except bbpbcnException as exc:
        if typedef and fallback:
            return _decode_protobuf(data, {}, config)
        else:
            raise exc
    raise bbpbcnException(
        '解码 protobuf 失败，但未捕获 "none" 解码器。这种情况不应发生'
    )


# 此函数为一个文本文件派生编辑器。文件保存后，
# 会调用 `callback` 并传入用户保存的文本。如果 `callback` 抛出
# 异常，此函数会向用户显示错误，并允许
# 用户选择：继续编辑 payload、将 payload 重置为原始
# 文本并重新编辑，或者放弃并不做任何更改退出。
#
# UI 要求所有修改文本的逻辑都嵌入在
# 回调中，我找不到不需要回调就能获取用户选择的方法。
#
# 此函数有点复杂，因为我们不得不使用自定义的 chooser
# 类来允许递归的 chooser 调用，否则每个命令只允许一个
# 提示。希望以后能找到更好的处理方式。
T = TypeVar("T")


def _spawn_validating_editor(
    text: str, callback: Callable[[str], None], original_text: Optional[str] = None
) -> None:
    user_text = ctx.master.spawn_editor(text)
    if original_text is None:
        original_text = text

    try:
        callback(user_text)
        signals.pop_view_state.send()
    except Exception as exc:
        options = ["继续编辑", "重置 payload 并编辑", "退出"]

        def choose_callback(action: str):
            if action == "继续编辑":
                # 继续编辑失败的文本
                _spawn_validating_editor(user_text, callback, original_text)
            elif action == "重置 payload 并编辑":
                # 改为编辑原始文本
                _spawn_validating_editor(original_text, callback)
            elif action == "退出":
                # 直接返回
                signals.pop_view_state.send()
                return
            else:
                raise Exception(
                    f"验证编辑菜单中收到未知选项: {action}"
                )

        signals.pop_view_state.send()
        ctx.master.overlay(
            RecursiveChooser(
                ctx.master,
                f"验证 payload 时出错: {exc}",
                options,
                "",
                choose_callback,
            )
        )


# 以下是 `overlay.Chooser` 的精确按键实现，但是
# 没有在回调之后调用 `signals.pop_view_state.send()`。这允许我们
# 从回调函数中派生覆盖层（例如另一个 chooser）。
# 使用 `overlay.Chooser`，它会在回调*之后*调用 `signals.pop_view_state.send()`，
# 从而弹出由回调设置的新 chooser。
#
# 因此，调用 `signals.pop_view_state.send()` 的责任转移到了
# 回调函数，它应该在退出时或在弹出新的 chooser 之前调用。
class RecursiveChooser(overlay.Chooser):
    def keypress(self, size, key):
        key = self.master.keymap.handle_only("chooser", key)
        choice = self.walker.choice_by_shortcut(key)
        if choice:
            self.callback(choice)
            return
        if key == "m_select":
            self.callback(self.choices[self.walker.index])
            return
        elif key in ["q", "esc"]:
            signals.pop_view_state.send()
            return

        binding = self.master.keymap.get("global", key)
        # 这非常尴尬。我们需要更好的方法来仅匹配导航键。
        if binding and binding.command.startswith("console.nav"):
            self.master.keymap.handle("global", key)
        elif key in keymap.navkeys:
            return super().keypress(size, key)


addons = [bbpbcnAddon()]
