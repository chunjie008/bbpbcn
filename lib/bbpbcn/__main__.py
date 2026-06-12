# 版权所有 (c) 2018-2024 NCC Group Plc
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

import sys
import json
import base64
import binascii
import argparse
import io

import typing
from typing import Any, Dict, Optional, Tuple

from .lib.exceptions import bbpbcnException
from .lib import api
from .lib import payloads
from .lib import packdiff
from .lib import protofile
from .lib import db
from .lib import hexconvert
from .lib import packetanalyzer
from .lib.pytypes import TypeDefDict, Message


def _build_parser():
    # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(description="Blackbox Protobuf CLI")
    subparsers = parser.add_subparsers(dest="command")

    convert_parser = subparsers.add_parser(
        "convert", help="将十六进制字符串转换为各种类型（整数、浮点数、字符串等）"
    )
    convert_parser.add_argument(
        "hex_str",
        nargs="?",
        help="要转换的十六进制字符串（如果未提供，则从标准输入读取）。"
        "支持的格式：01020304, 01 02 03 04, 01-02-03-04, 0x01020304",
    )
    convert_parser.add_argument(
        "-t",
        "--type",
        required=True,
        dest="convert_type",
        choices=sorted(hexconvert.TYPE_MAP.keys()) + ["string", "hex_raw", "bits"],
        help="转换的目标类型",
    )
    convert_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        dest="convert_json",
        help="以 JSON 格式输出结果",
    )

    analyze_parser = subparsers.add_parser(
        "analyze", help="分析十六进制数据包并检测结构（长度、消息ID、唯一ID、protobuf）"
    )
    analyze_parser.add_argument(
        "packets",
        nargs="*",
        help="十六进制数据包字符串（如果未提供，则从标准输入读取）。"
        "支持的格式：01020304, 01 02 03 04, 01-02-03-04, 0x01020304",
    )
    analyze_parser.add_argument(
        "-e",
        "--endian",
        choices=["le", "be"],
        default="le",
        help="字节序（默认为 le）",
    )
    analyze_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        dest="analyze_json",
        help="以 JSON 格式输出结果",
    )

    diff_parser = subparsers.add_parser(
        "diff", help="对比两个 protobuf 消息的字段差异"
    )
    diff_parser.add_argument(
        "msg1",
        help="第一个消息（hex 字符串，或 --json-input 时的 JSON 字符串）",
    )
    diff_parser.add_argument(
        "msg2",
        help="第二个消息（hex 字符串，或 --json-input 时的 JSON 字符串）",
    )
    diff_parser.add_argument(
        "-t",
        "--typedef",
        dest="diff_typedef",
        help="用于解码的 typedef JSON 文件",
    )
    diff_parser.add_argument(
        "--json-input",
        action="store_true",
        dest="diff_json_input",
        help="输入已经是解码后的 JSON 消息而非 hex",
    )
    diff_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        dest="diff_json_output",
        help="以 JSON 格式输出差异结果",
    )

    proto_parser = subparsers.add_parser(
        "proto", help="导入/导出 .proto 文件"
    )
    proto_subparsers = proto_parser.add_subparsers(dest="proto_action")

    proto_export_parser = proto_subparsers.add_parser(
        "export", help="将 typedef 导出为 .proto 格式"
    )
    proto_export_parser.add_argument(
        "-i",
        "--input",
        required=True,
        dest="proto_input",
        help="输入的 typedef JSON 文件",
    )
    proto_export_parser.add_argument(
        "-n",
        "--name",
        dest="proto_name",
        help="消息名称（当 typedef 为裸字典时使用）",
    )
    proto_export_parser.add_argument(
        "-p",
        "--package",
        dest="proto_package",
        help="proto 包名",
    )

    proto_import_parser = proto_subparsers.add_parser(
        "import", help="从 .proto 文件导入 typedef"
    )
    proto_import_parser.add_argument(
        "-i",
        "--input",
        required=True,
        dest="proto_input",
        help="输入的 .proto 文件",
    )
    proto_import_parser.add_argument(
        "--save",
        action="store_true",
        dest="proto_save",
        help="保存到 known_types 配置中",
    )

    _db_build_parser(subparsers)

    parser.add_argument(
        "-e",
        "--encode",
        action="store_true",
        help="切换到编码模式。默认情况下命令执行解码操作",
    )
    parser.add_argument(
        "-j",
        "--json-protobuf",
        action="store_true",
        help='使用可能包含 base64 编码的 protobuf 和typedef 的 JSON 对象，而不是仅包含原始 protobuf 字节作为编码输入和解码输出。JSON 可能包含以下键："message", "typedef", "payload_encoding"。',
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="使用紧凑/非美化 JSON 输出",
    )
    parser.add_argument(
        "-pe",
        "--payload-encoding",
        action="store",
        help="覆盖 payload 的包装编码，例如 gzip 或 grpc",
    )
    parser.add_argument(
        "-it",
        "--input-type",
        action="store",
        help="从文件读取 typedef 而不是从标准输入",
    )
    parser.add_argument(
        "-ot",
        "--output-type",
        action="store",
        help='（解码）将 typedef 写入文件而不是标准输出。此文件可以是普通 JSON typedef 或包含 "typedef" 和 "payload_encoding" 字段的 JSON 对象。',
    )
    parser.add_argument(
        "-r",
        "--raw-decode",
        action="store_true",
        help="（解码）仅输出解码后的 JSON，不输出类型信息。",
    )
    return parser


def main():
    # type: () -> int
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "convert":
        return _convert(args)

    if args.command == "analyze":
        return _analyze(args)

    if args.command == "diff":
        return _diff(args)

    if args.command == "proto":
        return _proto(args)

    if args.command == "db":
        return _db(args)

    # 原始的 protobuf 解码/编码逻辑

    message = None  # type:  str | bytes | Message | None
    typedef = None  # type: TypeDefDict | None
    payload_encoding = None  # type: str | None

    if args.input_type:
        typedef, payload_encoding = _read_input_typedef_arg(args)

    if args.payload_encoding:
        payload_encoding = args.payload_encoding

    input_data = _read_input(args)
    if args.encode:
        input_json = json.loads(input_data)
        message, typedef, payload_encoding = _read_input_json_encoding(
            args, input_json, typedef, payload_encoding
        )
    elif args.json_protobuf:
        input_json = json.loads(input_data)
        message, typedef, payload_encoding = _read_input_json_decoding(
            args, input_json, typedef, payload_encoding
        )
    else:
        message = input_data

    if payload_encoding is None:
        payload_encoding = "none"

    # 开始基本的原始 protobuf 解码
    if args.encode:
        if not isinstance(message, dict):
            sys.stderr.write("错误：未获取到有效的待编码消息")
            return 1
        if typedef is None:
            sys.stderr.write("编码需要一个有效的类型定义")
            return 1
        return _encode(args, message, typedef, payload_encoding)
    else:
        if isinstance(message, str):
            message = message.encode("utf-8")
        if not isinstance(message, bytes):
            sys.stderr.write("错误：未获取到有效的待解码消息")
            return 1
        return _decode(args, message, typedef, payload_encoding)


def _convert(args):
    # type: (argparse.Namespace) -> int
    if args.hex_str:
        try:
            result = hexconvert.convert_hex(args.hex_str, args.convert_type)
            if args.convert_json:
                sys.stdout.write(
                    json.dumps(
                        {
                            "hex": args.hex_str,
                            "type": args.convert_type,
                            "value": result,
                        },
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
            else:
                sys.stdout.write(str(result) + "\n")
        except (ValueError, binascii.Error) as e:
            sys.stderr.write("错误：%s\n" % e)
            return 1
    else:
        lines = sys.stdin.read().strip().splitlines()
        if not lines:
            sys.stderr.write("错误：未提供十六进制输入\n")
            return 1
        output = hexconvert.convert_hex_lines(lines, args.convert_type, args.convert_json)
        sys.stdout.write(output + "\n")
    return 0


def _analyze(args):
    # type: (argparse.Namespace) -> int
    if args.packets:
        hex_strings = args.packets
    else:
        hex_strings = [
            line.strip()
            for line in sys.stdin.read().strip().splitlines()
            if line.strip()
        ]
    if not hex_strings:
        sys.stderr.write("错误：未提供十六进制数据包\n")
        return 1
    try:
        result = packetanalyzer.analyze_packets(hex_strings, args.endian)
        if args.analyze_json:
            sys.stdout.write(packetanalyzer.format_json(result))
        else:
            sys.stdout.write(packetanalyzer.format_text(result))
        return 0
    except (ValueError, binascii.Error) as e:
        sys.stderr.write("错误：%s\n" % e)
        return 1


def _diff(args):
    # type: (argparse.Namespace) -> int
    try:
        if args.diff_json_input:
            msg1 = json.loads(args.msg1)
            msg2 = json.loads(args.msg2)
        else:
            typedef = None
            if args.diff_typedef:
                with open(args.diff_typedef, "r") as f:
                    typedef = json.load(f)
            raw1 = binascii.unhexlify(args.msg1.replace(" ", "").replace("-", "").replace("0x", "").replace("0X", ""))
            raw2 = binascii.unhexlify(args.msg2.replace(" ", "").replace("-", "").replace("0x", "").replace("0X", ""))
            msg1_json, _ = api.protobuf_to_json(raw1, typedef)
            msg2_json, _ = api.protobuf_to_json(raw2, typedef)
            msg1 = json.loads(msg1_json)
            msg2 = json.loads(msg2_json)

        changes = packdiff.diff_messages(msg1, msg2)

        if args.diff_json_output:
            sys.stdout.write(packdiff.format_json(changes))
        else:
            sys.stdout.write(packdiff.format_diff(changes))
        return 0
    except (ValueError, binascii.Error) as e:
        sys.stderr.write("错误：%s\n" % e)
        return 1


def _proto(args):
    # type: (argparse.Namespace) -> int
    try:
        if args.proto_action == "export":
            with open(args.proto_input, "r") as f:
                data = json.load(f)

            typedef_map = {}  # type: Dict[str, TypeDefDict]
            if args.proto_name:
                typedef_map[args.proto_name] = data
            elif isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                typedef_map = data
            else:
                sys.stderr.write("错误：请使用 -n 指定消息名称\n")
                return 1

            output = protofile.export_proto(typedef_map, package=args.proto_package)
            if output:
                sys.stdout.write(output)
            return 0

        elif args.proto_action == "import":
            result = api.import_protofile(args.proto_input, save_to_known=args.proto_save)
            if not args.proto_save and result:
                sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            return 0

        else:
            sys.stderr.write("错误：请指定 proto 操作：export 或 import\n")
            return 1

    except (ValueError, IOError, Exception) as e:
        sys.stderr.write("错误：%s\n" % e)
        return 1


def _db_build_parser(subparsers):
    # type: (argparse._SubParsersAction) -> None
    db_parser = subparsers.add_parser("db", help="持久化数据库管理")
    db_sub = db_parser.add_subparsers(dest="db_action")

    db_sub.add_parser("init", help="初始化数据库（创建表）")

    import_parser = db_sub.add_parser("import", help="导入一条 hex 封包")
    import_parser.add_argument("hex", nargs="?", help="hex 字符串（未提供时从 stdin 读取）")
    import_parser.add_argument("-m", "--msgid", type=int, default=0, help="消息 ID")
    import_parser.add_argument("-p", "--project", default="", help="项目/游戏名")
    import_parser.add_argument("-d", "--direction", default="", help="方向 (C2S/S2C)")
    import_parser.add_argument("-D", "--describe", default="", help="功能描述")
    import_parser.add_argument("-r", "--remark", default="", help="备注")

    importdir_parser = db_sub.add_parser("import-dir", help="批量导入目录中的 hex 文件")
    importdir_parser.add_argument("dir", help="目录路径")
    importdir_parser.add_argument("-m", "--msgid", type=int, required=True, help="消息 ID")
    importdir_parser.add_argument("-p", "--project", default="", help="项目/游戏名")
    importdir_parser.add_argument("-d", "--direction", default="", help="方向 (C2S/S2C)")

    list_parser = db_sub.add_parser("list", help="列出消息")
    list_parser.add_argument("-p", "--project", default="", help="按项目筛选")
    list_parser.add_argument("--status", default="", help="按状态筛选 (pending/analyzing/confirmed)")
    list_parser.add_argument("-m", "--msgid", type=int, default=None, help="按 msgid 筛选")
    list_parser.add_argument("-l", "--limit", type=int, default=50, help="限制条数")
    list_parser.add_argument("--json", action="store_true", dest="list_json", help="JSON 输出")

    get_parser = db_sub.add_parser("get", help="查看单条消息详情")
    get_parser.add_argument("id", type=int, help="消息 ID")
    get_parser.add_argument("--json", action="store_true", dest="get_json", help="JSON 输出")

    update_parser = db_sub.add_parser("update", help="更新消息字段")
    update_parser.add_argument("id", type=int, help="消息 ID")
    update_parser.add_argument("--project", help="项目名")
    update_parser.add_argument("--msgid", type=int, help="消息 ID")
    update_parser.add_argument("--direction", help="方向")
    update_parser.add_argument("--hex", help="hex payload")
    update_parser.add_argument("--typedef", dest="update_typedef", help="typedef JSON 文件路径")
    update_parser.add_argument("--describe", help="功能描述")
    update_parser.add_argument("--remark", help="备注")
    update_parser.add_argument("--status", choices=["pending", "analyzing", "confirmed"], help="状态")

    delete_parser = db_sub.add_parser("delete", help="删除消息")
    delete_parser.add_argument("id", type=int, help="消息 ID")

    search_parser = db_sub.add_parser("search", help="全文搜索")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("-p", "--project", default="", help="按项目限定")
    search_parser.add_argument("--json", action="store_true", dest="search_json", help="JSON 输出")

    stats_parser = db_sub.add_parser("stats", help="统计信息")
    stats_parser.add_argument("-p", "--project", default="", help="按项目统计")
    stats_parser.add_argument("--json", action="store_true", dest="stats_json", help="JSON 输出")

    export_parser = db_sub.add_parser("export", help="导出 typedef")
    export_parser.add_argument("--id", type=int, dest="export_id", help="单条消息 ID")
    export_parser.add_argument("-p", "--project", default="", help="按项目导出")
    export_parser.add_argument("-f", "--format", choices=["proto", "json"], default="proto", dest="export_format", help="导出格式")

    history_parser = db_sub.add_parser("history", help="typedef 变更历史")
    history_parser.add_argument("id", type=int, help="消息 ID")
    history_parser.add_argument("--json", action="store_true", dest="history_json", help="JSON 输出")

    session_parser = db_sub.add_parser("session", help="分析会话管理")
    session_sub = session_parser.add_subparsers(dest="session_action")

    sc_parser = session_sub.add_parser("create", help="创建会话")
    sc_parser.add_argument("-p", "--project", required=True, help="项目名")
    sc_parser.add_argument("-n", "--name", required=True, help="会话名称")
    sc_parser.add_argument("-m", "--msg-ids", dest="msg_ids", help="关联的消息 ID 列表，逗号分隔")
    sc_parser.add_argument("--notes", default="", help="备注")

    sl_parser = session_sub.add_parser("list", help="列出会话")
    sl_parser.add_argument("-p", "--project", default="", help="按项目筛选")
    sl_parser.add_argument("--json", action="store_true", dest="slist_json", help="JSON 输出")

    sg_parser = session_sub.add_parser("get", help="查看会话详情")
    sg_parser.add_argument("id", type=int, help="会话 ID")
    sg_parser.add_argument("--json", action="store_true", dest="sget_json", help="JSON 输出")

    sd_parser = session_sub.add_parser("delete", help="删除会话")
    sd_parser.add_argument("id", type=int, help="会话 ID")


def _db(args):
    # type: (argparse.Namespace) -> int
    d = db.BbpDB()
    try:
        if args.db_action == "init":
            sys.stdout.write("数据库已就绪: %s\n" % d.db_path)
            return 0

        if args.db_action == "import":
            hex_str = args.hex
            if not hex_str:
                hex_str = sys.stdin.read().strip()
            if not hex_str:
                sys.stderr.write("错误：未提供 hex 输入\n")
                return 1
            hex_str = _clean_hex(hex_str)
            mid = d.insert_message(
                hex=hex_str,
                msgid=args.msgid,
                project=args.project,
                direction=args.direction,
                describe=args.describe,
                remark=args.remark,
            )
            sys.stdout.write("已导入: id=%d  msgid=%d  project=%s\n" % (mid, args.msgid, args.project or "(无)"))
            return 0

        if args.db_action == "import-dir":
            import os
            import glob
            if not os.path.isdir(args.dir):
                sys.stderr.write("错误：目录不存在: %s\n" % args.dir)
                return 1
            files = sorted(glob.glob(os.path.join(args.dir, "*.hex"))) or sorted(os.listdir(args.dir))
            count = 0
            for fname in files:
                fpath = os.path.join(args.dir, fname) if not os.path.isabs(fname) else fname
                if not os.path.isfile(fpath):
                    continue
                with open(fpath, "r") as f:
                    h = f.read().strip()
                h = _clean_hex(h)
                if not h:
                    continue
                d.insert_message(hex=h, msgid=args.msgid, project=args.project, direction=args.direction)
                count += 1
            sys.stdout.write("已导入 %d 条 (msgid=%d, project=%s)\n" % (count, args.msgid, args.project or "(无)"))
            return 0

        if args.db_action == "list":
            rows = d.list_messages(
                project=args.project or None,
                status=args.status or None,
                msgid=args.msgid,
                limit=args.limit,
            )
            if args.list_json:
                _db_dump_json([dict(r) for r in rows])
            else:
                _db_print_list(rows)
            return 0

        if args.db_action == "get":
            row = d.get_message(args.id)
            if not row:
                sys.stderr.write("错误：未找到 id=%d\n" % args.id)
                return 1
            if args.get_json:
                _db_dump_json(dict(row))
            else:
                _db_print_detail(row)
            return 0

        if args.db_action == "update":
            updates = {}
            for src, dst in [
                ("project", "project"), ("msgid", "msgid"),
                ("direction", "direction"), ("hex", "hex"),
                ("describe", "describe"), ("remark", "remark"),
                ("status", "status"),
            ]:
                v = getattr(args, src, None)
                if v is not None:
                    updates[dst] = v
            if args.update_typedef:
                with open(args.update_typedef, "r") as f:
                    updates["typedef"] = f.read()
            if not updates:
                sys.stderr.write("错误：未指定要更新的字段\n")
                return 1
            ok = d.update_message(args.id, **updates)
            sys.stdout.write(("已更新 id=%d\n" if ok else "错误：未找到 id=%d\n") % args.id)
            return 0 if ok else 1

        if args.db_action == "delete":
            ok = d.delete_message(args.id)
            sys.stdout.write(("已删除 id=%d\n" if ok else "错误：未找到 id=%d\n") % args.id)
            return 0 if ok else 1

        if args.db_action == "search":
            rows = d.search_messages(args.keyword, project=args.project or None)
            if args.search_json:
                _db_dump_json([dict(r) for r in rows])
            else:
                _db_print_list(rows)
            return 0

        if args.db_action == "stats":
            s = d.stats(project=args.project or None)
            if args.stats_json:
                _db_dump_json(s)
            else:
                _db_print_stats(s, project=args.project or None)
            return 0

        if args.db_action == "export":
            if args.export_id:
                typedefs = d.export_typedefs(message_ids=[args.export_id])
            else:
                typedefs = d.export_typedefs(project=args.project or None)
            if args.export_format == "proto":
                out = protofile.export_proto(typedefs)
                if out:
                    sys.stdout.write(out)
            else:
                _db_dump_json(typedefs)
            return 0

        if args.db_action == "history":
            rows = d.get_history(args.id)
            if args.history_json:
                _db_dump_json([dict(r) for r in rows])
            elif not rows:
                sys.stdout.write("  id=%d 无 typedef 变更历史\n" % args.id)
            else:
                sys.stdout.write("  typedef 变更历史 (id=%d):\n" % args.id)
                for r in rows:
                    sys.stdout.write("    v%d (%s):\n" % (r["version"], r["changed_at"]))
                    fmt = _db_pretty_typedef(r["typedef"])
                    for L in fmt.split("\n"):
                        sys.stdout.write("      %s\n" % L)
            return 0

        if args.db_action == "session":
            return _db_session(args, d)

        sys.stderr.write("错误：未知的 db 操作: %s\n" % args.db_action)
        return 1
    finally:
        d.close()


def _db_session(args, d):
    # type: (argparse.Namespace, db.BbpDB) -> int
    if args.session_action == "create":
        msg_ids = [int(x.strip()) for x in args.msg_ids.split(",")] if args.msg_ids else []
        sid = d.create_session(project=args.project, name=args.name, msg_ids=msg_ids, notes=args.notes)
        sys.stdout.write("已创建会话: id=%d  %s/%s\n" % (sid, args.project, args.name))
        return 0

    if args.session_action == "list":
        rows = d.list_sessions(project=args.project or None)
        if args.slist_json:
            _db_dump_json([dict(r) for r in rows])
        elif not rows:
            sys.stdout.write("  (无会话)\n")
        else:
            sys.stdout.write("  会话列表:\n")
            for r in rows:
                sys.stdout.write("    #%-4d  %-20s  %s\n" % (r["id"], r["name"], r["project"]))
        return 0

    if args.session_action == "get":
        row = d.get_session(args.id)
        if not row:
            sys.stderr.write("错误：未找到会话 id=%d\n" % args.id)
            return 1
        if args.sget_json:
            _db_dump_json(dict(row))
        else:
            sys.stdout.write("  会话 (id=%d):\n" % row["id"])
            sys.stdout.write("    项目: %s\n" % row["project"])
            sys.stdout.write("    名称: %s\n" % row["name"])
            sys.stdout.write("    消息: %s\n" % row["msg_ids"])
            sys.stdout.write("    备注: %s\n" % row["notes"])
            sys.stdout.write("    创建: %s\n" % row["created_at"])
        return 0

    if args.session_action == "delete":
        ok = d.delete_session(args.id)
        sys.stdout.write(("已删除会话 id=%d\n" if ok else "未找到会话 id=%d\n") % args.id)
        return 0

    sys.stderr.write("错误：请指定 session 操作\n")
    return 1


# ── db 辅助函数 ──

def _clean_hex(s):
    # type: (str) -> str
    return s.replace(" ", "").replace("-", "").replace("\n", "").replace("\r", "").replace("\t", "")


def _db_dump_json(data):
    # type: (object) -> None
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def _db_print_list(rows):
    # type: (list[sqlite3.Row]) -> None
    if not rows:
        sys.stdout.write("  (无记录)\n")
        return
    sys.stdout.write("  %-4s  %-6s  %-18s  %-10s  %s\n" % ("ID", "MSGID", "PROJECT", "STATUS", "DESCRIBE"))
    sys.stdout.write("  " + "-" * 70 + "\n")
    for r in rows:
        sys.stdout.write("  %-4d  %-6d  %-18s  %-10s  %s\n" % (
            r["id"], r["msgid"], r["project"][:18], r["status"], r["describe"][:30],
        ))


def _db_print_detail(row):
    # type: (sqlite3.Row) -> None
    sys.stdout.write("  id:        %d\n" % row["id"])
    sys.stdout.write("  msgid:     %d\n" % row["msgid"])
    sys.stdout.write("  project:   %s\n" % row["project"])
    sys.stdout.write("  direction: %s\n" % row["direction"])
    sys.stdout.write("  status:    %s\n" % row["status"])
    sys.stdout.write("  describe:  %s\n" % row["describe"])
    sys.stdout.write("  remark:    %s\n" % row["remark"])
    sys.stdout.write("  created:   %s\n" % row["created_at"])
    sys.stdout.write("  updated:   %s\n" % row["updated_at"])
    h = row["hex"]
    sys.stdout.write("  hex:       %s%s\n" % (h[:80], "..." if len(h) > 80 else ""))
    sys.stdout.write("  typedef:\n")
    fmt = _db_pretty_typedef(row["typedef"])
    for L in fmt.split("\n"):
        sys.stdout.write("    %s\n" % L)


def _db_pretty_typedef(typedef_str):
    # type: (str) -> str
    try:
        obj = json.loads(typedef_str) if typedef_str else {}
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return typedef_str or "{}"


def _db_print_stats(s, project=None):
    # type: (dict, str | None) -> None
    sys.stdout.write("  ")
    if project:
        sys.stdout.write("项目: %s  " % project)
    sys.stdout.write("总计: %d 条消息\n" % s["total"])
    if s["by_msgid"]:
        sys.stdout.write("  按 msgid:\n")
        for item in s["by_msgid"]:
            sys.stdout.write("    %s: %d\n" % (item["msgid"], item["count"]))
    if s["by_status"]:
        sys.stdout.write("  按状态:\n")
        for item in s["by_status"]:
            sys.stdout.write("    %s: %d\n" % (item["status"], item["count"]))
    if s["by_direction"]:
        sys.stdout.write("  按方向:\n")
        for item in s["by_direction"]:
            sys.stdout.write("    %s: %d\n" % (item["direction"] or "(无)", item["count"]))


# 从 args 指定的位置读取输入
# 不处理任何 JSON 解码
def _read_input(args):
    # type: (argparse.Namespace) -> str | bytes
    if args.encode or args.json_protobuf:
        # 文本
        return sys.stdin.read()
    else:
        # 二进制
        return sys.stdin.buffer.read()


# 将输出写入 args 指定的位置
# 不处理任何 JSON 编码
def _write_output(args, data):
    # type: (argparse.Namespace, str | bytes) -> None
    if isinstance(data, str):
        # 文本
        sys.stdout.write(data)
    else:
        # 二进制
        sys.stdout.buffer.write(data)


def _read_input_typedef_arg(args):
    # type: (argparse.Namespace) -> Tuple[TypeDefDict, Optional[str]]
    with open(args.input_type, "r") as f:
        input_json = json.load(f)
    if "typedef" in input_json:
        return input_json.get("typedef"), input_json.get("payload_encoding")
    else:
        # 将整个 payload 作为 typedef 返回，无编码
        return input_json, None


def _write_output_typedef_arg(args, typedef):
    # type: (argparse.Namespace, Dict[str, str | TypeDefDict]) -> None
    with open(args.output_type, "w") as f:
        f.write(_to_json(args, typedef))


def _to_json(args, data):
    # type: (argparse.Namespace, Dict[str, Any]) -> str
    if args.compact:
        return json.dumps(data)
    else:
        return json.dumps(data, indent=2)


def _read_input_json_encoding(args, input_json, typedef, payload_encoding):
    # type: (argparse.Namespace, Message | Dict[str, str | Message | TypeDefDict], Optional[TypeDefDict], Optional[str]) -> Tuple[Message, Optional[TypeDefDict], Optional[str]]
    if typedef is None and "typedef" not in input_json:
        sys.stderr.write(
            "错误：未从 --input-type 或标准输入获取 typedef。编码需要 typedef\n"
        )
        sys.exit(1)

    message = typing.cast(Message | None, input_json.get("message"))
    if message is None:
        # 整个输入就是消息。我们已经确保有 typedef，所以可以丢弃它
        return typing.cast(Message, input_json), typedef, None

    if typedef is None:
        typedef = typing.cast(TypeDefDict | None, input_json.get("typedef"))

    if payload_encoding is None:
        json_payload_encoding = input_json.get("payload_encoding")
        if isinstance(json_payload_encoding, str):
            payload_encoding = json_payload_encoding
        elif json_payload_encoding is None:
            payload_encoding = None
        else:
            sys.stderr.write(
                "警告：Payload 编码必须是字符串值：%r" % payload_encoding
            )
            payload_encoding = None

    return message, typedef, payload_encoding


def _read_input_json_decoding(args, input_json, typedef, payload_encoding):
    # type: (argparse.Namespace, Dict[str, TypeDefDict | str], Optional[TypeDefDict], Optional[str]) -> Tuple[bytes, Optional[TypeDefDict], Optional[str]]
    # 返回 message, typedef, payload_encoding
    message = typing.cast(str | None, input_json.get("protobuf_data"))
    if message is None:
        sys.stderr.write('错误：输入 JSON 中未包含 "protobuf_data" 属性')
        sys.exit(1)

    if typedef is None:
        typedef = typing.cast(TypeDefDict | None, input_json.get("typedef"))

    if payload_encoding is None:
        payload_encoding = typing.cast(str | None, input_json.get("payload_encoding"))

    # 当使用 protobuf_json 时进行 base64 解码
    protobuf_data = base64.b64decode(message)

    return protobuf_data, typedef, payload_encoding


def _encode(args, message, typedef, payload_encoding):
    # type: (argparse.Namespace, Message, TypeDefDict, Optional[str]) -> int
    if typedef is None:
        sys.stderr.write("错误：没有有效的 typedef 无法编码")
        return 1

    if not payload_encoding:
        payload_encoding = "none"

    # 重新 JSON 化以便 bbpbcn 可以处理字节
    message_json = json.dumps(message)

    protobuf_data = api.protobuf_from_json(message_json, typedef)

    data = payloads.encode_payload(protobuf_data, payload_encoding)

    if args.json_protobuf:
        json_out = {
            "protobuf_data": base64.b64encode(data).decode("ascii"),
            "typedef": typedef,  # 这里的 typedef 有点冗余
        }
        if payload_encoding != "none":
            json_out["payload_encoding"] = payload_encoding

        _write_output(args, _to_json(args, json_out))
    else:
        _write_output(args, data)
    return 0


def _decode(args, data, typedef, payload_encoding):
    # type: (argparse.Namespace, bytes, Optional[TypeDefDict], str) -> int
    if len(data) == 0:
        sys.stderr.write("错误：输入数据不能为空\n")
        return 1

    # args.protobuf_json 已处理

    if payload_encoding:
        # 使用提供的 payload 编码算法
        protobuf_data, payload_encoding = payloads.decode_payload(
            data, payload_encoding
        )
        message_json, output_typedef = api.protobuf_to_json(protobuf_data, typedef)
    else:
        # 需要猜测解码算法
        decoders = payloads.find_decoders(data)

        for decode in decoders:
            try:
                protobuf_data, encoding_alg = decode(data)
            except bbpbcnException:
                # "none" 算法应该总是成功的
                continue

            try:
                message_json, output_typedef = api.protobuf_to_json(
                    protobuf_data, typedef
                )
                break
            except bbpbcnException as exc:
                if encoding_alg == "none":
                    raise exc

    message = json.loads(message_json)

    if args.output_type:
        output_typedef_data = {}  # type: Dict[str, TypeDefDict | str]
        output_typedef_data["typedef"] = output_typedef
        if payload_encoding != "none":
            output_typedef_data["payload_encoding"] = payload_encoding
        _write_output_typedef_arg(args, output_typedef_data)

    if args.raw_decode:
        output = message
    else:
        output = {
            "message": message,
            "typedef": output_typedef,
        }
        if payload_encoding != "none":
            output["payload_encoding"] = payload_encoding
    _write_output(args, _to_json(args, output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
