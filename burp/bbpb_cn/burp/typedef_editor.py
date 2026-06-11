"""包含用于编辑类型定义的窗口的类。可从消息编辑器选项卡
和套件选项卡调用。
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

import traceback
import json
import bbpb_cn
from java.awt import Component, Dimension, Frame
from java.awt.event import ActionListener, WindowEvent
from javax.swing import (
    JSplitPane,
    JPanel,
    JButton,
    BoxLayout,
    JOptionPane,
    JDialog,
    Box,
    JTextField,
)


class TypeEditorWindow(JDialog):
    """用于编辑指定类型定义的新独立窗口。保存类型时将
    回调到调用类
    """

    def __init__(self, burp_callbacks, typedef, source, callback):
        burp_window = None
        for frame in Frame.getFrames():
            if "Burp Suite" in frame.getName():
                burp_window = frame
                break
        JDialog.__init__(self, burp_window)
        self._burp_callbacks = burp_callbacks
        self._type_callback = callback
        self.setSize(1000, 700)

        self._original_typedef = typedef
        self._type_source = source
        self._original_json = json.dumps(self._original_typedef, indent=4)
        self._type_editor = burp_callbacks.createTextEditor()
        self._type_editor.setEditable(True)
        self._type_editor.setText(self._original_json)

        splitPane = JSplitPane(JSplitPane.HORIZONTAL_SPLIT)
        splitPane.setLeftComponent(self._type_editor.getComponent())
        splitPane.setRightComponent(self.createButtonPane())
        splitPane.setResizeWeight(0.8)

        self.add(splitPane)

        self.is_open = True

    def createButtonPane(self):
        """在类型编辑器窗口中创建新的按钮面板"""
        self._button_listener = TypeEditorButtonListener(self)

        panel = JPanel()
        panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))

        panel.add(Box.createRigidArea(Dimension(0, 5)))
        panel.add(
            self.createButton("Validate", "validate", "检查 typedef 是否有效")
        )
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(self.createButton("Save", "save", "保存 typedef"))
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(self.createButton("Reset", "reset", "重置为原始内容"))
        panel.add(Box.createRigidArea(Dimension(0, 3)))
        panel.add(self.createButton("Exit", "exit", "关闭窗口并重置"))
        panel.add(Box.createRigidArea(Dimension(0, 3)))

        return panel

    def createButton(self, text, command, tooltip):
        """使用给定的文本和命令生成新按钮"""
        button = JButton(text)
        button.setAlignmentX(Component.CENTER_ALIGNMENT)
        button.setActionCommand(command)
        button.addActionListener(self._button_listener)
        button.setToolTipText(tooltip)
        return button

    def applyType(self):
        """应用按钮的回调。验证定义并调用
        打开窗口时提供的回调
        """

        try:
            new_json = self._type_editor.getText().tostring()
            message_type = json.loads(new_json)
            if self._original_json == new_json and len(message_type) != 0:
                # 检测文本是否未更改，但允许空类型用于添加空的类型
                self.exitTypeWindow()
                return

            bbpb_cn.validate_typedef(message_type, self._original_typedef)

            self._type_callback(message_type, self._type_source)
            self.exitTypeWindow()

        except Exception as exc:
            self._burp_callbacks.printError(traceback.format_exc())
            JOptionPane.showMessageDialog(self, "Error saving type: " + str(exc))

    def resetTypeWindow(self):
        """重置按钮的回调。重置为原始类型定义"""
        self._type_editor.setText(json.dumps(self._original_typedef, indent=4))

    def exitTypeWindow(self):
        """退出按钮的回调。不保存退出窗口"""
        self.is_open = False
        self.dispatchEvent(WindowEvent(self, WindowEvent.WINDOW_CLOSING))

    def validateType(self):
        """验证按钮的回调。验证类型而不保存"""
        try:
            message_type = json.loads(self._type_editor.getText().tostring())
        except Exception as exc:
            self._burp_callbacks.printError(traceback.format_exc())
            JOptionPane.showMessageDialog(self, "Error decoding JSON: " + str(exc))
            return

        try:
            bbpb_cn.validate_typedef(message_type, self._original_typedef)
        except Exception as exc:
            self._burp_callbacks.printError(traceback.format_exc())
            JOptionPane.showMessageDialog(self, "Error validating type: " + str(exc))
            return


class TypeEditorButtonListener(ActionListener):
    """类型编辑器窗口的按钮动作监听器"""

    def __init__(self, type_editor):
        self._type_editor = type_editor

    def actionPerformed(self, event):
        """当按钮被按下时调用"""
        if event.getActionCommand() == "validate":
            self._type_editor.validateType()
        elif event.getActionCommand() == "save":
            self._type_editor.applyType()
        elif event.getActionCommand() == "reset":
            self._type_editor.resetTypeWindow()
        elif event.getActionCommand() == "exit":
            self._type_editor.exitTypeWindow()
