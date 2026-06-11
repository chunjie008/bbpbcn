"""添加顶层类型定义编辑器并注册各个选项卡的 protobuf 消息
编辑器工厂
"""

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
import traceback
import burp
import json
from javax.swing import DefaultListModel
from java.util.concurrent import Executors


# 将正确的目录添加到 sys.path
_BASE_DIR = os.path.abspath(
    os.path.dirname(inspect.getfile(inspect.currentframe())) + "../../../../"
)
sys.path.insert(0, _BASE_DIR + "/burp/")

import bbpb_cn
from bbpb_cn.lib.config import default as default_config
from bbpb_cn.burp import editor, typedef_tab, typedef_editor


EXTENSION_NAME = "bbpb_cn"


class BurpExtender(burp.IBurpExtender, burp.IExtensionStateListener):
    """主要的扩展类。设置所有其他功能。"""

    def __init__(self):
        self.open_windows = []
        self.callbacks = None
        self.helpers = None
        self.saved_types = {}
        self.suite_tab = None
        # 所有视图的已知消息全局列表
        # 这应与 bbpb_cn.known_messages 中的内容保持一致
        # TODO 将它们捆绑在一起，这样就不需要手动更新了
        self.known_message_model = DefaultListModel()
        self.refresh_message_model()

        self.thread_executor = Executors.newCachedThreadPool()

    def refresh_message_model(self):
        self.known_message_model.clear()
        for name in default_config.known_types.keys():
            self.known_message_model.addElement(name)

    def registerExtenderCallbacks(self, callbacks):
        """由 Burp 调用。收集回调对象并设置 UI"""
        try:
            callbacks.registerExtensionStateListener(self)

            self.callbacks = callbacks

            self.helpers = callbacks.getHelpers()

            callbacks.setExtensionName(EXTENSION_NAME)

            callbacks.registerMessageEditorTabFactory(
                editor.ProtoBufEditorTabFactory(self, callbacks)
            )

            self.suite_tab = typedef_tab.TypeDefinitionTab(self, callbacks)
            callbacks.addSuiteTab(self.suite_tab)
            self.loadKnownMessages()
            self.refresh_message_model()
        except Exception as exc:
            self.callbacks.printError(traceback.format_exc())
            raise exc

    def loadKnownMessages(self):
        message_json = self.callbacks.loadExtensionSetting("known_types")
        if message_json:
            default_config.known_types.update(json.loads(message_json))
        saved_types = self.callbacks.loadExtensionSetting("saved_type_map")
        if saved_types:
            self.saved_types.update(json.loads(saved_types))

    def saveKnownMessages(self):
        # TODO 也许更频繁地调用这个会更好（例如，当消息更新时）
        # 保存已知的消息
        self.callbacks.saveExtensionSetting(
            "known_types", json.dumps(default_config.known_types)
        )
        self.callbacks.saveExtensionSetting(
            "saved_type_map", json.dumps(self.saved_types)
        )

    def extensionUnloaded(self):
        self.thread_executor.shutdownNow()
        self.saveKnownMessages()
        for window in self.open_windows:
            window.exitTypeWindow()

    def open_typedef_editor(self, message_type, source, callback):
        self.open_windows = [window for window in self.open_windows if window.is_open]

        window = typedef_editor.TypeEditorWindow(
            self.callbacks,
            message_type,
            source,
            callback,
        )
        window.show()

        self.open_windows.append(window)
