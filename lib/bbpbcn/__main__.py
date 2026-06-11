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

import typing
from typing import Any, Dict, Optional, Tuple

from .lib.exceptions import bbpbcnException
from .lib import api
from .lib import payloads
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

    # 重新 JSON 化以便 bbpb 可以处理字节
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
