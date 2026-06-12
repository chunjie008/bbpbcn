# 版权所有 (c) 2018-2024 NCC Group Plc
#
# 特此免费授予任何获得本软件及相关文档文件（"软件"）副本的人，不受限制地处理
# 本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或
# 销售本软件副本的权利，并允许获得本软件的人这样做，但须符合以下条件：
#
# 上述版权声明和本许可声明应包含在本软件的所有副本或实质性部分中。
#
# 本软件按"原样"提供，不作任何明示或暗示的担保，包括但不限于对适销性、特定
# 用途适用性和非侵权的担保。在任何情况下，作者或版权持有人均不对因使用本软件
# 而产生的任何索赔、损害或其他责任承担责任，无论是合同行为、侵权行为还是其他
# 行为。

import json


def diff_messages(msg1, msg2):
    # type: (dict, dict) -> list[dict]
    changes = []
    _compare("", msg1, msg2, changes)
    return changes


def _compare(path, v1, v2, changes):
    # type: (str, object, object, list[dict]) -> None
    if v1 == v2:
        return
    if isinstance(v1, dict) and isinstance(v2, dict):
        all_keys = set(v1.keys()) | set(v2.keys())
        for key in sorted(all_keys, key=str):
            sub = "%s.%s" % (path, key) if path else str(key)
            if key not in v1:
                changes.append({"path": sub, "type": "added", "new": v2[key]})
            elif key not in v2:
                changes.append({"path": sub, "type": "removed", "old": v1[key]})
            else:
                _compare(sub, v1[key], v2[key], changes)
    elif isinstance(v1, list) and isinstance(v2, list):
        for i in range(max(len(v1), len(v2))):
            sub = "%s[%d]" % (path, i)
            if i >= len(v1):
                changes.append({"path": sub, "type": "added", "new": v2[i]})
            elif i >= len(v2):
                changes.append({"path": sub, "type": "removed", "old": v1[i]})
            else:
                _compare(sub, v1[i], v2[i], changes)
    else:
        changes.append({
            "path": path or "(root)",
            "type": "changed",
            "old": v1,
            "new": v2,
        })


def _short_val(v):
    # type: (object) -> str
    if isinstance(v, dict):
        return "{...}"
    if isinstance(v, list):
        return "[%d items]" % len(v)
    return json.dumps(v, ensure_ascii=False)


def format_diff(changes):
    # type: (list[dict]) -> str
    if not changes:
        return "  \u65e0\u5dee\u5f02\n"
    lines = ["  \u5b57\u6bb5\u5dee\u5f02:"]
    for c in changes:
        if c["type"] == "added":
            lines.append("    + %s: %s" % (c["path"], _short_val(c["new"])))
        elif c["type"] == "removed":
            lines.append("    - %s: %s" % (c["path"], _short_val(c["old"])))
        elif c["type"] == "changed":
            lines.append("    ~ %s: %s -> %s" % (c["path"], _short_val(c["old"]), _short_val(c["new"])))
    return "\n".join(lines) + "\n"


def format_json(changes):
    # type: (list[dict]) -> str
    return json.dumps(changes, indent=2, ensure_ascii=False, default=str)
