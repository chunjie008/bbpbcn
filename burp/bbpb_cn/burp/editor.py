"""包含创建 Protobuf 编辑器选项卡所需的类。"""

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

import re
import six
import traceback
import base64
import zlib
import burp
import copy
import struct
import bbpb_cn
from javax.swing import JSplitPane, JPanel, JButton, BoxLayout, JOptionPane
from javax.swing import (
    Box,
    JTextField,
    JScrollPane,
    JList,
    ListSelectionModel,
    ListModel,
)
from javax.swing.event import ListSelectionListener, ListDataEvent, ListDataListener
from java.awt import Component, Dimension, FlowLayout
from java.awt.event import ActionListener
from javax.swing.border import EmptyBorder
from bbpb_cn.burp import user_funcs
from bbpb_cn.burp import typedef_editor
from bbpb_cn.lib import payloads
from bbpb_cn.lib.config import default as default_config
from bbpb_cn.lib.exceptions import (
    bbpb_cnException,
    DecoderException,
    EncoderException,
)

NAME_REGEX = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]*\Z")


class ProtoBufEditorTabFactory(burp.IMessageEditorTabFactory):
    """仅返回 ProtoBufEditorTab 实例"""

    def __init__(self, extender, callbacks):
        self._callbacks = callbacks
        self._extender = extender

    def createNewInstance(self, controller, editable):
        """返回新消息的编辑器选项卡新实例"""
        return ProtoBufEditorTab(self._extender, controller, editable, self._callbacks)


class ProtoBufEditorTab(burp.IMessageEditorTab):
    """在拦截器/重放器中用于编辑 protobuf 消息的选项卡。

    将消息解码为 JSON 以便编辑，再编码回 protobuf。
    消息类型定义附加到此对象，用于重新编码或编辑。
    """

    def __init__(self, extension, controller, editable, callbacks):
        self._callbacks = callbacks
        self._extension = extension
        self._callbacks = extension.callbacks
        self._helpers = extension.helpers

        self._controller = controller

        self._text_editor = self._callbacks.createTextEditor()
        self._text_editor.setEditable(editable)
        self._editable = editable

        self._last_valid_type_index = None

        self._filtered_message_model = FilteredMessageModel(
            extension.known_message_model, self._callbacks
        )

        self._type_list_component = JList(self._filtered_message_model)
        self._type_list_component.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self._type_list_component.addListSelectionListener(TypeListListener(self))

        self._new_type_field = JTextField()

        self._component = JSplitPane(JSplitPane.HORIZONTAL_SPLIT)
        self._component.setLeftComponent(self._text_editor.getComponent())
        self._component.setRightComponent(self.createButtonPane())
        self._component.setResizeWeight(0.95)

        self._message_info = None
        self._payload_info = None
        self._last_good_msg = None  # (msg, typedef, source)
        self._decode_task = None

    def getTabCaption(self):
        """返回消息选项卡标题"""
        return "Protobuf"

    def getMessage(self):
        """将 JSON 格式转换回二进制 protobuf 消息"""
        # 注意到这个函数由于某种原因被调用了两次
        # 如果消息解码尚未完成，则取消并返回原始内容
        if self._decode_task and (
            not self._decode_task.isDone() or self._decode_task.isCancelled()
        ):
            self._decode_task.cancel(True)
            self._decode_task = None
            # self._callbacks.printOutput(
            #    "Called getMessage before decode task was done, returning original content"
            # )
            return self._message_info.content()

        if self._last_good is None or not self.isModified():
            return self._message_info.content()

        success = False
        try:
            json_data = self._text_editor.getText().tostring()
            protobuf_data = bbpb_cn.protobuf_from_json(
                json_data, self._last_good.typedef
            )

            success = True
            self._payload_info.protobuf_data = protobuf_data
            return self._payload_info.generate_http(self._message_info, self._helpers)

        except Exception as exc:
            self._callbacks.printError(traceback.format_exc())

        if not success:
            try:
                protobuf_data = bbpb_cn.protobuf_from_json(
                    self._last_good.message, self._last_good.typedef
                )

                # 在此处放置错误，以便如果上述编码不起作用，用户只看到一个错误
                JOptionPane.showMessageDialog(
                    self._component,
                    "Error encoding protobuf as-is. Reset data to previous good state: "
                    + str(exc),
                )

                success = True
                # 同时重置消息和 protobuf 数据
                self._text_editor.setText(self._last_good.message)
                self._payload_info.protobuf_data = protobuf_data
                return self._payload_info.generate_http(
                    self._message_info, self._helpers
                )
            except Exception as exc:
                self._callbacks.printError(traceback.format_exc())
                JOptionPane.showMessageDialog(
                    self._component,
                    "Error encoding protobuf. Setting data to the original message. Error: "
                    + str(exc),
                )
                self._text_editor.setText(self._message_info.content())
                return self._message_info.content()

    def _handle_protobuf(
        self, message_info, protobuf_data, message_type_in, typedef_source
    ):
        """
        设置编辑器的 protobuf 消息。
        """
        try:
            json_data, message_type = bbpb_cn.protobuf_to_json(
                protobuf_data, message_type_in
            )

            self._last_good = LastGoodData(json_data, message_type, typedef_source)
            self._filtered_message_model.set_new_data(protobuf_data)
            self._text_editor.setText(json_data)  # UI access
            success = True
        except Exception as exc:
            success = False
            self._callbacks.printError(
                "Got error decoding protobuf binary: " + traceback.format_exc()
            )

        # 移出异常处理器以避免嵌套
        if success:
            if typedef_source is not None:
                self.forceSelectType(typedef_source)
            else:
                self._type_list_component.clearSelection()
        elif len(message_type_in) == 0:
            self._callbacks.printError(
                "Error decoding protobuf with saved type, trying with empty type"
            )
            self._handle_protobuf(message_info, protobuf_data, {}, None)
        else:
            self._callbacks.printError("Error decoding protobuf with empty type")
            self._text_editor.setText("Error decoding protobuf")

    def setMessage(self, content, is_request):
        """
        从请求/响应中获取数据并解析为 JSON。
        """
        # 在单独线程中运行以避免 Burp UI 挂起
        # 已观察到当消息较大时 Burp UI 可能会挂起
        # 且解码过程需要很长时间

        message_info = MessageInfo(content, is_request, self._helpers, self._controller)
        payload_info = PayloadInfo(message_info, self._helpers)
        message_type, typedef_source = self._get_saved_typedef(message_info)

        if (
            self._decode_task
            and not self._decode_task.isCancelled()
            and not self._decode_task.isDone()
        ):
            # 如果正在处理的消息与运行中的任务相同
            # 检查消息哈希值
            # 检查 protobuf 数据
            # TODO 我们是否要检查 typedef？可以切换离开再回来以重新启动
            if (
                message_info.message_hash == self._message_info.message_hash
                and payload_info.raw_data == self._payload_info.raw_data
            ):
                # self._callbacks.printOutput(
                #    "Switched to tab that is still running with the same hash and payload. Not cancelling."
                # )
                return
            else:
                # self._callbacks.printOutput(
                #    "Have existing task that is still running, cancelling"
                # )
                # 取消旧任务
                self._decode_task.cancel(True)

        self._message_info = message_info
        self._payload_info = payload_info
        self._last_good_msg = None
        self._decode_task = None

        self._text_editor.setText("Please wait...")

        def run():
            try:
                decoders = payloads.find_decoders(payload_info.raw_data)
                for decoder in decoders:
                    try:
                        protobuf_data, encoding_alg = decoder(payload_info.raw_data)
                    except bbpb_cnException:
                        continue

                    try:
                        self._handle_protobuf(
                            message_info,
                            protobuf_data,
                            message_type,
                            typedef_source,
                        )

                        # Payload 成功解码，所以我们可能找到了正确的 payload 包装器
                        self._payload_info.protobuf_data = protobuf_data
                        self._payload_info.encoding_alg = encoding_alg

                        return
                    except bbpb_cnException:
                        if encoding_alg == "none":
                            # 将异常重新抛出到父上下文并停止解码
                            six.reraise(*sys.exc_info())
                        continue

            except Exception as ex:
                # 捕获所有异常，否则会消失
                self._text_editor.setText("Error decoding protobuf")
                self._callbacks.printError("Error decoding protobuf: %s" % ex)

        self._decode_task = self._extension.thread_executor.submit(run)

    def getSelectedData(self):
        """获取当前在消息中选中的文本"""
        return self._text_editor.getSelectedText()

    def getUiComponent(self):
        """返回此选项卡的 Java AWT 组件"""
        return self._component

    def isEnabled(self, content, is_request):
        """尝试检测消息中的 protobuf 以启用选项卡。

        默认检查 'x-protobuf' 的 content-type 头。用户可在 `user_funcs.py` 中覆盖。
        """
        # TODO 实现更多默认检查
        if is_request:
            info = self._helpers.analyzeRequest(content)
        else:
            info = self._helpers.analyzeResponse(content)

        if "detect_protobuf" in dir(user_funcs):
            result = user_funcs.detect_protobuf(
                content, is_request, info, self._helpers
            )
            if result is not None:
                return result

        # 如果没有 body 则提前退出
        if info.getBodyOffset() == len(content):
            return False

        protobuf_content_types = [
            "protobuf",
            "grpc",
        ]
        # 检查所有头部中是否包含 protobuf
        for header in info.getHeaders():
            if "content-type" in header.lower():
                for protobuf_content_type in protobuf_content_types:
                    if protobuf_content_type in header.lower():
                        return True

        return False

    def isModified(self):
        """返回消息是否被修改"""
        return self._text_editor.isTextModified()

    def createButtonPane(self):
        """为消息编辑器选项卡创建新的按钮面板"""
        self._button_listener = EditorButtonListener(self)

        panel = JPanel()
        panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))
        panel.setBorder(EmptyBorder(5, 5, 5, 5))

        panel.add(Box.createRigidArea(Dimension(0, 5)))
        type_scroll_pane = JScrollPane(self._type_list_component)
        type_scroll_pane.setMaximumSize(Dimension(200, 100))
        type_scroll_pane.setMinimumSize(Dimension(150, 100))
        panel.add(type_scroll_pane)
        panel.add(Box.createRigidArea(Dimension(0, 3)))

        new_type_panel = JPanel()
        new_type_panel.setLayout(BoxLayout(new_type_panel, BoxLayout.X_AXIS))
        new_type_panel.add(self._new_type_field)
        new_type_panel.add(Box.createRigidArea(Dimension(3, 0)))
        new_type_panel.add(
            self.createButton(
                "New", "new-type", "以新名称保存此消息的类型"
            )
        )
        new_type_panel.setMaximumSize(Dimension(200, 20))
        new_type_panel.setMinimumSize(Dimension(150, 20))

        panel.add(new_type_panel)

        button_panel = JPanel()
        button_panel.setLayout(FlowLayout())
        if self._editable:
            button_panel.add(
                self.createButton(
                    "Validate", "validate", "验证消息是否可以编码。"
                )
            )
        button_panel.add(
            self.createButton("Edit Type", "edit-type", "编辑消息类型")
        )
        button_panel.add(
            self.createButton(
                "Reset Message", "reset", "重置消息并撤销更改"
            )
        )
        button_panel.add(
            self.createButton(
                "Clear Type", "clear-type", "使用空类型重新解析消息"
            )
        )
        button_panel.setMinimumSize(Dimension(100, 200))
        button_panel.setPreferredSize(Dimension(200, 1000))

        panel.add(button_panel)

        return panel

    def createButton(self, text, command, tooltip):
        """使用给定的文本和命令创建新按钮"""
        button = JButton(text)
        button.setAlignmentX(Component.CENTER_ALIGNMENT)
        button.setActionCommand(command)
        button.addActionListener(self._button_listener)
        button.setToolTipText(tooltip)
        return button

    def validateMessage(self):
        """验证按钮的回调。尝试使用当前类型定义编码消息"""
        try:
            json_data = self._text_editor.getText().tostring()
            typedef = self._last_good.typedef
            protobuf_data = bbpb_cn.protobuf_from_json(json_data, typedef)
            # 如果成功，保存消息
            # 不需要保存 typedef，因为我们使用的是 lastgood 中的那个
            self._last_good.message = json_data
            self._payload_info.protobuf_data = protobuf_data

        except Exception as exc:
            JOptionPane.showMessageDialog(
                self._component,
                "Got exception while trying to encode the message: " + str(exc),
            )
            self._callbacks.printError(traceback.format_exc())

    def resetMessage(self):
        """放弃所有更改并恢复到上一个正确的消息。"reset" 按钮的回调"""

        self._text_editor.setText(self._last_good.message)

    def forceSelectType(self, typename):
        index = self._filtered_message_model.get_type_index(typename)
        if index is not None:
            self._last_valid_type_index = index
            self._type_list_component.setSelectedIndex(index)

    def updateTypeSelection(self):
        """根据在类型列表中选择的类型应用新的 typedef"""
        # TODO 如果我们意外点击了一个类型就丢失匿名类型，这很糟糕。也许应该在列表中添加一个缓存类型的条目？
        # 或者在切换前给出警告
        # 或者需要点击 + 按钮确认？

        # 检查是否选择了某个类型
        if self._type_list_component.isSelectionEmpty():
            self._last_valid_type_index = None
            self._extension.saved_types.pop(self._message_info.message_hash, None)
            return

        # TODO 如果删除正在使用的类型，而新类型现在在索引中，这将无法正常工作
        if self._last_valid_type_index == self._type_list_component.getSelectedIndex():
            # 自上次尝试以来实际上没有变化
            # 否则在下面失败时调用 setSelectedIndex 会第二次触发
            return

        type_name = self._type_list_component.getSelectedValue()
        # 尝试捕获 None...
        if not type_name or type_name not in default_config.known_types:
            return

        try:
            self.applyType(default_config.known_types[type_name], type_name)
        except bbpb_cnException as exc:
            self._callbacks.printError(traceback.format_exc())

            if isinstance(exc, EncoderException):
                JOptionPane.showMessageDialog(
                    self._component,
                    "Error encoding protobuf with previous type: %s" % (exc),
                )
            elif isinstance(exc, DecoderException):
                JOptionPane.showMessageDialog(
                    self._component,
                    "Error encoding protobuf with type %s: %s" % (type_name, exc),
                )
                # 解码器异常意味着该类型与先前类型成功编码的消息不匹配
                self._filtered_message_model.remove_type(type_name)

            if self._last_valid_type_index is not None:
                type_name = self._type_list_component.setSelectedIndex(
                    self._last_valid_type_index
                )
            else:
                self._type_list_component.clearSelection()
            return

        self._extension.saved_types[self._message_info.message_hash] = type_name
        self._last_valid_type_index = self._type_list_component.getSelectedIndex()

    def editType(self, typedef, source):
        """应用并保存新的 typedef"""
        # 先尝试应用类型
        try:
            # TODO 像 handle_protobuf 一样在后台执行此操作？我认为需要
            # 更确定我们可以验证 typedef 而无需先解码
            # 这里的解码会抛出异常，如果类型无效将阻止我们
            # 关闭 typedef 编辑器窗口
            self.applyType(typedef, source)
        except bbpb_cnException as exc:
            self._callbacks.printError("Got exception trying to apply edited typedef.")
            JOptionPane.showMessageDialog(
                self._component,
                "Error decoding the protobuf with the new type: %s" % (exc),
            )
            return

        if source is None:
            # 绑定到消息哈希的匿名 typedef
            # 保存 typedef
            self._extension.saved_types[self._message_info.message_hash] = typedef
        else:
            # 命名 typedef
            # 保存到已知 typedef 下，并在 source 中保存名称
            default_config.known_types[source] = typedef
            self._extension.saved_types[self._message_info.message_hash] = source

    def applyType(self, typedef, source):
        """对消息应用新的 typedef。如果类型无效则抛出异常。"""
        # 使用旧类型转换为 protobuf，再重新解释为新类型
        old_typedef = self._last_good.typedef
        json_data = self._text_editor.getText().tostring()

        protobuf_data = bbpb_cn.protobuf_from_json(json_data, old_typedef)
        self._payload_info.protobuf_data = protobuf_data

        new_json, new_typedef = bbpb_cn.protobuf_to_json(
            protobuf_data, typedef
        )

        self._last_good = LastGoodData(new_json, new_typedef, source)

        self._filtered_message_model.set_new_data(protobuf_data)
        self._text_editor.setText(str(new_json))
        # 我们不在此处记住类型，这应由调用者处理

    def saveAsNewType(self):
        """将当前类型复制到 known_messages 中"""

        name = self._new_type_field.getText().strip()
        if not NAME_REGEX.match(name):
            JOptionPane.showMessageDialog(
                self._component,
                "%s is not a valid "
                "message name. Message names should be alphanumeric." % name,
            )
            return
        if name in default_config.known_types:
            JOptionPane.showMessageDialog(
                self._component, "Message name %s is " "already taken." % name
            )
            return

        typedef = self._last_good.typedef

        # 对字典进行深拷贝，以免意外修改其他内容
        default_config.known_types[name] = copy.deepcopy(typedef)
        self._last_good.source = name  # 记住来源，typedef 仍然相同

        # 更新消息列表。这应传递到已知消息模型
        self._extension.known_message_model.addElement(name)
        self._new_type_field.setText("")
        self._extension.saved_types[self._message_info.message_hash] = name

        # 强制选择我们的新类型
        self.forceSelectType(name)

    def clearType(self):
        self.applyType({}, None)
        self._type_list_component.clearSelection()
        self._new_type_field.setText("")
        self._extension.saved_types.pop(self._message_info.message_hash, None)

    def open_typedef_window(self):
        typedef = self._last_good.typedef
        source = self._last_good.source
        self._extension.open_typedef_editor(typedef, source, self.editType)

    def _get_saved_typedef(self, message_info):
        # 获取为此消息保存的 typedef
        # 可以是匿名的，但基于消息哈希保存
        # 也可以是命名的
        # 返回 typedef, typename 元组
        if message_info.message_hash in self._extension.saved_types:
            saved_type = self._extension.saved_types[message_info.message_hash]
            if isinstance(saved_type, dict):
                return saved_type, None
            elif saved_type in default_config.known_types:
                typename = saved_type
                typedef = default_config.known_types[typename]
                return typedef, typename
            else:
                # 我们有一个类型，但它既不是 dict 也不在已知类型中
                # 错误，因此清除
                self._extension.saved_types.pop(message_info.message_hash, None)
                self._callbacks.printError(
                    "Found unknown saved type: %s for %s"
                    % (saved_type, message_info.message_hash)
                )
        else:
            return {}, None


class EditorButtonListener(ActionListener):
    """消息编辑器选项卡中按钮的回调监听器"""

    def __init__(self, editor_tab):
        self._editor_tab = editor_tab

    def actionPerformed(self, event):
        """当消息编辑器中的按钮被按下时调用"""
        if event.getActionCommand() == "validate":
            self._editor_tab.validateMessage()
        elif event.getActionCommand() == "reset":
            self._editor_tab.resetMessage()
        elif event.getActionCommand() == "edit-type":
            self._editor_tab.open_typedef_window()
        elif event.getActionCommand() == "new-type":
            self._editor_tab.saveAsNewType()
        elif event.getActionCommand() == "clear-type":
            self._editor_tab.clearType()


class TypeListListener(ListSelectionListener):
    """从列表中选择新类型时的回调监听器"""

    def __init__(self, editor_tab):
        self._editor_tab = editor_tab

    def valueChanged(self, event):
        if event.getValueIsAdjusting():
            return
        self._editor_tab.updateTypeSelection()


class FilteredMessageModel(ListModel, ListDataListener):
    """监听 java ListModel 并维护仅包含消息有效类型的子集"""

    def __init__(self, parent, callbacks):
        self._callbacks = callbacks
        self._data = None
        self._parent_model = parent
        self._listeners = []

        # 父模型中的类型列表
        self._types = []
        self._parent_types = set(parent.elements())
        self._rejected_types = set()
        self._working_types = set()

        self._parent_model.addListDataListener(self)

    def set_new_data(self, data):
        self._data = data

        # 清除缓存
        self._working_types.clear()
        self._rejected_types.clear()

        # 使用新数据重新检查所有类型
        for typename in self._types[:]:
            if not self._check_type(typename):
                removed_index = self._types.index(typename)
                self._types.remove(typename)
                event = ListDataEvent(
                    self, ListDataEvent.INTERVAL_REMOVED, removed_index, removed_index
                )
                self._send_event(event)

        interval_start = len(self._types)
        for typename in self._parent_types:
            if typename not in self._types and self._check_type(typename):
                self._types.append(typename)

        if len(self._types) > interval_start:
            event = ListDataEvent(
                self, ListDataEvent.INTERVAL_ADDED, interval_start, len(self._types) - 1
            )
            self._send_event(event)

    def get_type_index(self, typename):
        if typename in self._types:
            return self._types.index(typename)
        return None

    def remove_type(self, typename):
        # 如果应用类型失败，此方法允许我们将其移除
        if typename not in self._types:
            return

        type_index = self._types.index(typename)
        # 因为我们有索引，所以按索引删除
        del self._types[type_index]
        self._working_types.remove(typename)
        self._rejected_types.add(typename)

        event = ListDataEvent(
            self, ListDataEvent.INTERVAL_REMOVED, type_index, type_index
        )
        self._send_event(event)

    def update_types(self):
        new_parent_types = set(self._parent_model.elements())
        added_parent_types = new_parent_types - self._parent_types
        removed_parent_types = self._parent_types - new_parent_types
        self._parent_types = new_parent_types

        for type_name in removed_parent_types:
            if type_name in self._types:
                removed_index = self._types.index(type_name)
                self._types.remove(type_name)
                event = ListDataEvent(
                    self, ListDataEvent.INTERVAL_REMOVED, removed_index, removed_index
                )
                self._send_event(event)

        interval_start = len(self._types)
        for type_name in added_parent_types:
            if type_name not in self._types and self._check_type(type_name):
                self._types.append(type_name)

        # 不确定我们要投入多少精力处理事件。可以一直将所有内容标记为已更改
        if len(self._types) > interval_start:
            # 如果没有删除任何内容，则仅发出添加事件？
            event = ListDataEvent(
                self, ListDataEvent.INTERVAL_ADDED, interval_start, len(self._types) - 1
            )
            self._send_event(event)

    def _send_event(self, event):
        event_type = event.getType()
        if event_type == ListDataEvent.CONTENTS_CHANGED:
            for listener in self._listeners:
                listener.contentsChanged(event)
        elif event_type == ListDataEvent.INTERVAL_ADDED:
            for listener in self._listeners:
                listener.intervalAdded(event)
        elif event_type == ListDataEvent.INTERVAL_REMOVED:
            for listener in self._listeners:
                listener.intervalRemoved(event)

    def _check_type(self, typename):
        # TODO 此操作也会挂起 UI
        # TODO 通过比较 typedef 来检查比尝试解码更好
        if typename in self._rejected_types:
            return False
        if typename in self._working_types:
            return True

        # 如果还没有数据，提前退出
        if not self._data:
            return False
        if typename not in default_config.known_types:
            return False
        typedef = default_config.known_types[typename]
        try:
            _, _ = bbpb_cn.protobuf_to_json(self._data, typedef)
        except bbpb_cnException as exc:
            self._callbacks.printError(traceback.format_exc())
            self._rejected_types.add(typename)
            return False
        self._working_types.add(typename)
        return True

    def addListDataListener(self, listener):
        self._listeners.append(listener)

    def getElementAt(self, i):
        return self._types[i]

    def getSize(self):
        return len(self._types)

    def removeListDataListener(self, listener):
        self._listeners.remove(listener)

    # 数据监听器相关
    def contentsChanged(self, event):
        self.update_types()

    def intervalAdded(self, event):
        self.update_types()

    def intervalRemoved(self, event):
        self.update_types()


class MessageInfo:
    """此类解析从 Burp 获取的数据，供我们在整个处理过程中使用"""

    def __init__(self, content, is_request, helpers, controller):
        self.is_request = is_request

        if is_request:
            self.request = content
        else:
            self.request = controller.getRequest()

            self.response = content
            self.response_content_info = helpers.analyzeResponse(content)

        self.request_content_info = helpers.analyzeRequest(
            controller.getHttpService(), self.request
        )

        self.message_hash = self._message_hash(helpers)

    def content(self):
        if self.is_request:
            return self.request
        else:
            return self.response

    def content_info(self):
        if self.is_request:
            return self.request_content_info
        else:
            return self.response_content_info

    def _message_hash(self, helpers):
        """计算消息的"标识符"，用于粘性类型定义。用户可修改"""
        message_hash = None
        if "hash_message" in dir(user_funcs):
            message_hash = user_funcs.hash_message(
                self.content(),
                self.is_request,
                self.content_info(),
                helpers,
                self.request,
                self.request_content_info,
            )
        if message_hash is None:
            # 仅基于 URL 和请求/响应
            url = self.request_content_info.getUrl()
            message_hash = ":".join(
                [url.getAuthority(), url.getPath(), str(self.is_request)]
            )

        return message_hash


class PayloadInfo:
    """此类存储最新的 payload 数据以及将其与 HTTP 消息互相转换的函数"""

    def __init__(self, message_info, helpers):
        self.raw_data = None  # 来自 payload 的原始数据
        # 这些属性必须在此类外部设置
        self.encoding_alg = None
        self.protobuf_data = None  # 最后已知的正确编码的 protobuf payload
        self.parse_http(message_info, helpers)

    def parse_http(self, message_info, helpers):
        raw_data = None
        if "get_protobuf_data" in dir(user_funcs):
            raw_data = user_funcs.get_protobuf_data(
                message_info.content(),
                message_info.is_request,
                message_info.content_info(),
                helpers,
                message_info.request,
                message_info.request_content_info,
            )
        if raw_data is None:
            raw_data = message_info.content()[
                message_info.content_info().getBodyOffset() :
            ].tostring()
        self.raw_data = raw_data

    def generate_http(self, message_info, helpers):
        if "set_protobuf_data" in dir(user_funcs):
            result = user_funcs.set_protobuf_data(
                self.protobuf_data,
                message_info.content(),
                message_info.is_request,
                message_info.content_info(),
                helpers,
                message_info.request,
                message_info.request_content_info,
            )
            if result is not None:
                return result

        if self.protobuf_data is None:
            raise bbpb_cnException(
                "Error generating HTTP body. PayloadInfo does not have valid protobuf data to encode"
            )
        raw_data = payloads.encode_payload(self.protobuf_data, self.encoding_alg)
        headers = message_info.content_info().getHeaders()
        return helpers.buildHttpMessage(headers, str(raw_data))


class LastGoodData:
    """此类存储关于上一个有效的消息和 typedef 组合的数据"""

    def __init__(self, message, typedef, source):
        self.message = message
        self.typedef = typedef
        self.source = source
