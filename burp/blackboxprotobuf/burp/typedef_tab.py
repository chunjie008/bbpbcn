""" TypeDefinitionTab 是 Burp Suite 的顶层选项卡，允许随时添加/修改已保存/命名的
    类型。它还提供了将 protobuf 类型导入/导出到 .json 文件的选项。
"""

# Copyright (c) 2018-2023 NCC Group Plc
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import re
import json
import burp
import traceback
import blackboxprotobuf
from javax.swing import JSplitPane, JScrollPane, JPanel, JButton, BoxLayout, Box
from javax.swing import JOptionPane, JList, ListSelectionModel, JFileChooser
from javax.swing.filechooser import FileNameExtensionFilter
from java.awt import Component, Dimension
from java.awt.event import ActionListener
from javax.swing.border import EmptyBorder
from blackboxprotobuf.lib.api import sort_typedef
from blackboxprotobuf.lib.config import default as default_config

from blackboxprotobuf.burp import typedef_editor

# TODO 将这些放在一个地方
NAME_REGEX = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]*\Z")


class TypeDefinitionTab(burp.ITab):
    """实现编辑已知消息类型定义的接口。"""

    def __init__(self, extension, burp_callbacks):
        self._burp_callbacks = burp_callbacks
        self._extension = extension

        self._type_list_component = JList(extension.known_message_model)
        self._type_list_component.setSelectionMode(
            ListSelectionModel.MULTIPLE_INTERVAL_SELECTION
        )

        self._component = JPanel()
        self._component.setLayout(BoxLayout(self._component, BoxLayout.Y_AXIS))

        splitPane = JSplitPane(JSplitPane.HORIZONTAL_SPLIT)
        splitPane.setRightComponent(JScrollPane(self._type_list_component))
        splitPane.setLeftComponent(self.createButtonPane())
        splitPane.setResizeWeight(0.03)
        splitPane.setMaximumSize(Dimension(1000, 1000))

        self._component.add(splitPane)
        self._component.add(Box.createVerticalGlue())
        self._component.setBorder(EmptyBorder(10, 10, 10, 10))

    def getTabCaption(self):
        """返回选项卡名称"""
        return "Protobuf Type Editor"

    def getUiComponent(self):
        """返回选项卡的 Java AWT 组件"""
        return self._component

    def createButtonPane(self):
        """创建按钮的 AWT 窗口面板"""
        self._button_listener = TypeDefinitionButtonListener(self)

        panel = JPanel()
        panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))

        panel.add(Box.createRigidArea(Dimension(0, 5)))
        panel.add(self.createButton("Add", "new-type", "创建新类型"))
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(self.createButton("Edit", "edit-type", "编辑选中的类型"))
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton("Rename", "rename-type", "重命名选中的类型")
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton("Remove", "delete-type", "删除所有选中的类型")
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton(
                "Save All Types To File",
                "save-types",
                "将所有已知类型保存为 JSON 到文件",
            )
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton(
                "Load All Types From File", "load-types", "从 JSON 文件加载类型"
            )
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton(
                "Export All types As .proto",
                "export-proto",
                "将所有类型导出为 .proto",
            )
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(
            self.createButton(
                "Import .proto", "import-proto", "从 .proto 文件导入类型"
            )
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        return panel

    def createButton(self, text, command, tooltip):
        """使用给定的文本和命令字符串生成新按钮"""
        button = JButton(text)
        button.setAlignmentX(Component.CENTER_ALIGNMENT)
        button.setActionCommand(command)
        button.addActionListener(self._button_listener)
        button.setToolTipText(tooltip)
        return button

    def save_callback(self, typedef, name):
        """保存给定消息名称的 typedef 并更新列表"""
        if name not in default_config.known_types:
            self._extension.known_message_model.addElement(name)

        default_config.known_types[name] = typedef

    def add_typedef(self):
        type_name = JOptionPane.showInputDialog("Enter new name")

        # 如果已定义则报错
        if type_name in default_config.known_types:
            JOptionPane.showMessageDialog(
                self._component,
                'Message type "%s" already exists' % type_name,
            )
            return

        self._extension.open_typedef_editor({}, type_name, self.save_callback)

    def edit_typedef(self):
        list_component = self._type_list_component
        if list_component.isSelectionEmpty():
            return

        type_name = list_component.getSelectedValue()
        message_type = default_config.known_types[type_name]

        self._extension.open_typedef_editor(
            sort_typedef(message_type), type_name, self.save_callback
        )


class TypeDefinitionButtonListener(ActionListener):
    """TypeDefinition 界面中按钮的回调监听器"""

    def __init__(self, typedef_tab):
        self._typedef_tab = typedef_tab

    def actionPerformed(self, event):
        """当按钮被按下时调用。"""
        if event.getActionCommand() == "new-type":
            self._typedef_tab.add_typedef()

        elif event.getActionCommand() == "edit-type":
            self._typedef_tab.edit_typedef()

        elif event.getActionCommand() == "rename-type":
            list_component = self._typedef_tab._type_list_component
            # 检查是否选择了某个类型
            if list_component.isSelectionEmpty():
                return

            # 仅获取第一个值
            previous_type_name = list_component.getSelectedValue()
            new_type_name = JOptionPane.showInputDialog(
                "Enter new name for %s:" % previous_type_name
            )
            if new_type_name in default_config.known_types:
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    'Message type "%s" already exists' % new_type_name,
                )
                return
            if previous_type_name not in default_config.known_types:
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    'Message type "%s" does not exist' % previous_type_name,
                )
                return
            if not NAME_REGEX.match(new_type_name):
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    'Message type name "%s" is not valid.' % new_type_name,
                )
                return
            typedef = default_config.known_types[previous_type_name]
            default_config.known_types[new_type_name] = typedef
            del default_config.known_types[previous_type_name]
            # TODO 应该在某个地方集中管理这个
            self._typedef_tab._extension.refresh_message_model()
            for key, typename in self._typedef_tab._extension.saved_types.items():
                if typename == previous_type_name:
                    self._typedef_tab._extension.saved_types[key] = new_type_name

        elif event.getActionCommand() == "delete-type":
            list_component = self._typedef_tab._type_list_component
            # 检查是否选择了某个类型
            if list_component.isSelectionEmpty():
                return

            type_names = list_component.getSelectedValuesList()
            # TODO 确认删除？
            for type_name in type_names:
                del default_config.known_types[type_name]
            self._typedef_tab._extension.refresh_message_model()

        elif event.getActionCommand() == "save-types":
            chooser = JFileChooser()
            chooser.setFileFilter(
                FileNameExtensionFilter("JSON Type Definition", ["json"])
            )
            chooser.setMultiSelectionEnabled(False)

            action = chooser.showSaveDialog(self._typedef_tab.getUiComponent())
            if (
                action == JFileChooser.CANCEL_OPTION
                or action == JFileChooser.ERROR_OPTION
            ):
                return

            file_name = chooser.getSelectedFile().getCanonicalPath()
            ext = os.path.splitext(file_name)[1]
            if ext != ".json":
                # 如果没有扩展名则添加 json 扩展名
                file_name += ".json"

            with open(file_name, "w+") as selected_file:
                json.dump(
                    default_config.known_types,
                    selected_file,
                    indent=4,
                    sort_keys=True,
                )

        elif event.getActionCommand() == "load-types":
            chooser = JFileChooser()
            chooser.setFileFilter(
                FileNameExtensionFilter("JSON Type Definition", ["json"])
            )
            chooser.setMultiSelectionEnabled(False)

            action = chooser.showOpenDialog(self._typedef_tab.getUiComponent())
            if (
                action == JFileChooser.CANCEL_OPTION
                or action == JFileChooser.ERROR_OPTION
            ):
                return

            file_name = chooser.getSelectedFile().getCanonicalPath()
            types = {}
            with open(file_name, "r") as selected_file:
                types = json.load(selected_file)
            for key, value in types.items():
                # 检查以确保不会覆盖现有消息
                if key in default_config.known_types:
                    overwrite = (
                        JOptionPane.showConfirmDialog(
                            self._typedef_tab._component,
                            "Message %s already saved. Overwrite?" % key,
                        )
                        == 0
                    )
                    if not overwrite:
                        continue
                default_config.known_types[key] = value
            self._typedef_tab._extension.refresh_message_model()
        elif event.getActionCommand() == "export-proto":
            chooser = JFileChooser()
            chooser.setFileFilter(
                FileNameExtensionFilter("Protobuf Type Definition", ["proto"])
            )
            chooser.setMultiSelectionEnabled(False)

            action = chooser.showSaveDialog(self._typedef_tab.getUiComponent())
            if (
                action == JFileChooser.CANCEL_OPTION
                or action == JFileChooser.ERROR_OPTION
            ):
                return

            file_name = chooser.getSelectedFile().getCanonicalPath()
            ext = os.path.splitext(file_name)[1]
            if ext == "":
                # 无扩展名，添加 .proto
                file_name += ".proto"

            if os.path.exists(file_name):
                # 0 表示"是"选项
                overwrite = (
                    JOptionPane.showConfirmDialog(
                        self._typedef_tab._component,
                        "File %s already exists. Overwrite?" % file_name,
                    )
                    == 0
                )
                if not overwrite:
                    return
                print("overwriting file: %s" % file_name)
            try:
                blackboxprotobuf.export_protofile(default_config.known_types, file_name)
            except Exception as exc:
                self._typedef_tab._burp_callbacks.printError(traceback.format_exc())
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    "Error saving .proto file: " + str(exc),
                )

        elif event.getActionCommand() == "import-proto":
            chooser = JFileChooser()
            chooser.setFileFilter(
                FileNameExtensionFilter("Protobuf Type Definition", ["proto"])
            )
            chooser.setMultiSelectionEnabled(False)

            action = chooser.showOpenDialog(self._typedef_tab.getUiComponent())
            if (
                action == JFileChooser.CANCEL_OPTION
                or action == JFileChooser.ERROR_OPTION
            ):
                return

            file_name = chooser.getSelectedFile().getCanonicalPath()
            if not os.path.exists(file_name):
                self._typedef_tab._burp_callbacks.printError(
                    "Attempted to import %s, but the file does not exist." % file_name
                )
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    "File %s does not exist to import." + str(exc),
                )
                return
            try:
                new_typedefs = blackboxprotobuf.import_protofile(
                    file_name, save_to_known=False
                )
                for key, value in new_typedefs.items():
                    # 检查以确保不会覆盖现有消息
                    if key in default_config.known_types:
                        overwrite = (
                            JOptionPane.showConfirmDialog(
                                self._typedef_tab._component,
                                "Message %s already saved. Overwrite?" % key,
                            )
                            == 0
                        )
                        if not overwrite:
                            continue
                    else:
                        self._typedef_tab._extension.known_message_model.addElement(key)
                    default_config.known_types[key] = value
            except Exception as exc:
                self._typedef_tab._burp_callbacks.printError(traceback.format_exc())
                JOptionPane.showMessageDialog(
                    self._typedef_tab._component,
                    "Error loading .proto file: " + str(exc),
                )
