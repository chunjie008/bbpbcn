# Copyright (c) 2018-2024 NCC Group Plc
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

import struct
import json

from typing import Any, Dict, List, Optional

from . import hexconvert
from . import api
from .exceptions import BlackboxProtobufException

LEN_FMT_NAMES = ['uint16_le', 'uint16_be', 'uint32_le', 'uint32_be']
MSGID_FMT_NAMES = ['uint16_le', 'uint16_be', 'uint32_le', 'uint32_be']
UID_FMT_NAMES = ['uint32_le', 'uint32_be', 'uint64_le', 'uint64_be']


class Packet:
    # type: ignore
    def __init__(self, index, hex_str, raw):
        self.index = index
        self.hex_str = hex_str
        self.raw = raw
        self.size = len(raw)


def _parse_hex(hex_str):
    # type: (str) -> bytes
    return hexconvert._parse_hex(hex_str)


def _parse_all(hex_strings):
    # type: (List[str]) -> List[Packet]
    packets = []
    for i, h in enumerate(hex_strings):
        if not h.strip():
            continue
        raw = _parse_hex(h)
        packets.append(Packet(i + 1, h, raw))
    if not packets:
        raise ValueError("未提供有效的十六进制数据包")
    return packets


def _make_byte_mask(packets):
    # type: (List[Packet]) -> Dict
    max_len = max(p.size for p in packets)
    col_class = []
    for j in range(max_len):
        present = [p for p in packets if j < p.size]
        if len(present) <= 1:
            col_class.append('.')
        else:
            vals = set(p.raw[j] for p in present)
            col_class.append('C' if len(vals) == 1 else 'V')
    masks = []
    for p in packets:
        masks.append([
            col_class[j] if j < p.size else '.'
            for j in range(max_len)
        ])
    return {'max_len': max_len, 'masks': masks}


def _probe_field(packets, offset, fmt_name):
    # type: (List[Packet], int, str) -> Optional[Dict]
    if fmt_name not in hexconvert.TYPE_MAP:
        return None
    fmt, size, _ = hexconvert.TYPE_MAP[fmt_name]
    values = []
    for p in packets:
        if offset + size > p.size:
            return None
        val = struct.unpack(fmt, p.raw[offset:offset + size])[0]
        values.append(val)
    return {
        'offset': offset,
        'size': size,
        'type': fmt_name,
        'values': values,
    }


def _find_length_candidates(packets):
    # type: (List[Packet]) -> List[Dict]
    max_len = max(p.size for p in packets)
    candidates = []
    for offset in range(max(0, max_len - 1)):
        for fmt_name in LEN_FMT_NAMES:
            result = _probe_field(packets, offset, fmt_name)
            if result is None:
                continue
            values = result['values']
            size = result['size']

            score = 0
            match_type = None

            exact_total = all(values[i] == p.size for i, p in enumerate(packets))
            if exact_total:
                score += 50
                match_type = 'exact_total'

            exact_payload = all(values[i] == p.size - offset - size for i, p in enumerate(packets))
            if exact_payload:
                score += 40
                if match_type is None:
                    match_type = 'exact_payload'

            if all(1 <= v <= p.size * 2 for i, (v, p) in enumerate(zip(values, packets))):
                score += 5

            if all(v > 0 for v in values):
                score += 2

            candidates.append({
                'offset': offset,
                'size': size,
                'type': fmt_name,
                'values': values,
                'score': score,
                'match_type': match_type or 'none',
            })

    candidates.sort(key=lambda x: -x['score'])
    return candidates[:5]


def _find_msgid_candidates(packets, search_start):
    # type: (List[Packet], int) -> List[Dict]
    max_len = max(p.size for p in packets)
    candidates = []
    search_end = min(search_start + 16, max_len - 1)
    for offset in range(search_start, search_end):
        for fmt_name in MSGID_FMT_NAMES:
            result = _probe_field(packets, offset, fmt_name)
            if result is None:
                continue
            values = result['values']
            size = result['size']

            unique = set(values)
            max_val = max(values)
            min_val = min(values)

            score = 0

            if all(v > 0 for v in values):
                score += 2

            if 0 < max_val <= 65535:
                score += 3

            if min_val > 0:
                score += 1

            if len(unique) == 1:
                score += 3
            elif len(unique) <= max(2, len(packets) // 2):
                score += 5
            elif len(unique) <= max(3, len(packets) - 1):
                score += 2

            if max_val - min_val <= 100:
                score += 2

            candidates.append({
                'offset': offset,
                'size': size,
                'type': fmt_name,
                'values': values,
                'unique_count': len(unique),
                'score': score,
            })

    candidates.sort(key=lambda x: -x['score'])
    return candidates[:5]


def _find_uid_candidates(packets, search_start):
    # type: (List[Packet], int) -> List[Dict]
    max_len = max(p.size for p in packets)
    candidates = []
    search_end = min(search_start + 16, max_len)
    for offset in range(search_start, search_end):
        for fmt_name in UID_FMT_NAMES:
            result = _probe_field(packets, offset, fmt_name)
            if result is None:
                continue
            values = result['values']
            size = result['size']

            unique = set(values)
            max_val = max(values)
            min_val = min(values)

            score = 0

            if all(v > 0 for v in values):
                score += 1

            if len(unique) == 1 and max_val > 10000:
                score += 8
            elif len(unique) == 1:
                score += 5
            elif all(v > 10000 for v in values):
                score += 3

            if max_val - min_val <= 100:
                score += 1

            candidates.append({
                'offset': offset,
                'size': size,
                'type': fmt_name,
                'values': values,
                'unique_count': len(unique),
                'score': score,
            })

    candidates.sort(key=lambda x: -x['score'])
    return candidates[:5]


def _find_protobuf_payloads(packets, header_size):
    # type: (List[Packet], int) -> List[Dict]
    results = []
    for p in packets:
        payload = p.raw[header_size:]
        if not payload:
            results.append({'packet': p.index, 'valid': False, 'reason': 'empty'})
            continue
        try:
            message_json, typedef = api.protobuf_to_json(payload, None)
            results.append({
                'packet': p.index,
                'valid': True,
                'decoded': json.loads(message_json),
            })
        except (BlackboxProtobufException, Exception):
            results.append({'packet': p.index, 'valid': False, 'reason': 'decode_failed'})
    return results


def _pick_best(candidates):
    # type: (List[Dict]) -> Optional[Dict]
    if not candidates:
        return None
    top = candidates[0]
    if top['score'] <= 0:
        return None
    return top


def _confidence(score, max_score=50):
    # type: (int, int) -> str
    ratio = score / max_score if max_score else 0
    if ratio >= 0.7:
        return 'high'
    elif ratio >= 0.3:
        return 'medium'
    return 'low'


def analyze_packets(hex_strings, endian='le'):
    # type: (List[str], str) -> Dict[str, Any]
    packets = _parse_all(hex_strings)
    byte_mask = _make_byte_mask(packets)

    length_candidates = _find_length_candidates(packets)
    best_len = _pick_best(length_candidates)

    msgid_search_start = (best_len['offset'] + best_len['size']) if best_len else 0
    msgid_candidates = _find_msgid_candidates(packets, msgid_search_start)
    best_msgid = _pick_best(msgid_candidates)

    uid_search_start = (best_msgid['offset'] + best_msgid['size']) if best_msgid else msgid_search_start
    uid_candidates = _find_uid_candidates(packets, uid_search_start)
    best_uid = _pick_best(uid_candidates)

    header_end = 0
    for field in (best_len, best_msgid, best_uid):
        if field:
            header_end = max(header_end, field['offset'] + field['size'])
    proto_results = _find_protobuf_payloads(packets, header_end)

    return {
        'endian': endian,
        'packet_count': len(packets),
        'packets': [
            {'index': p.index, 'hex': p.hex_str, 'size': p.size, 'raw': p.raw}
            for p in packets
        ],
        'byte_mask': byte_mask,
        'length_candidates': length_candidates,
        'best_length_field': best_len,
        'msgid_candidates': msgid_candidates,
        'best_msgid_field': best_msgid,
        'uid_candidates': uid_candidates,
        'best_uid_field': best_uid,
        'header_size': header_end,
        'protobuf_results': proto_results,
    }


def _hex_row(raw_bytes):
    groups = []
    for i in range(0, len(raw_bytes), 2):
        chunk = raw_bytes[i:i+2]
        groups.append(' '.join(f'{b:02x}' for b in chunk))
    return '  '.join(groups)


def _format_field_candidate(label, candidate, show_values=True):
    if not candidate:
        return f"  {label}: （未检测到）\n"
    lines = [f"  {label}:"]
    lines.append(f"    {candidate['type']} @ 偏移 {candidate['offset']}")
    if show_values:
        lines.append(f"    值: {candidate['values']}")
    lines.append(f"    得分: {candidate['score']}")
    return '\n'.join(lines) + '\n'


def format_text(result):
    # type: (Dict) -> str
    lines = []
    lines.append('')
    lines.append('  数据包分析')
    lines.append('  ' + '\u2500' * 58)
    lines.append('')
    lines.append(f'  字节序: {result["endian"]},  数据包数: {result["packet_count"]}')
    lines.append('')

    for p in result['packets']:
        hex_str = _hex_row(p['raw'])
        lines.append(f'  #{p["index"]} ({p["size"]} B): {hex_str}')

    lines.append('')
    lines.append('  字节掩码（C=所有数据包恒定，V=可变）:')
    mask = result['byte_mask']

    header = '      '
    for i in range(mask['max_len']):
        header += f'{i:02x}  '
    lines.append(header)

    for idx, p in enumerate(result['packets']):
        row = f'  #{p["index"]}:  '
        for j in range(mask['max_len']):
            val = mask['masks'][idx][j]
            row += f'{val}    '
        lines.append(row)

    lines.append('')
    lines.append('  候选')
    lines.append('  ' + '\u2500' * 58)
    lines.append('')

    best = result.get('best_length_field')
    lines.append(_format_field_candidate('长度字段', best))
    if best:
        conf = _confidence(best['score'], 50)
        if best.get('match_type') == 'exact_total':
            lines.append(f'    匹配: 值 == 数据包总长度 [置信度: {conf}]')
        elif best.get('match_type') == 'exact_payload':
            lines.append(f'    匹配: 值 == payload 长度（总长度 - 偏移 - 大小） [置信度: {conf}]')
        elif best.get('match_type') == 'exact_lenfield_excluded':
            lines.append(f'    匹配: 值 == 总长度 - 2（长度字段排除自身） [置信度: {conf}]')
        else:
            lines.append(f'    匹配: 部分匹配 [置信度: {conf}]')
        lines.append('')

    best = result.get('best_msgid_field')
    lines.append(_format_field_candidate('消息ID字段', best))
    if best:
        conf = _confidence(best['score'], 15)
        lines.append(f'    唯一值数: {best["unique_count"]} [置信度: {conf}]')
        lines.append('')

    best = result.get('best_uid_field')
    lines.append(_format_field_candidate('唯一ID字段', best))
    if best:
        conf = _confidence(best['score'], 10)
        lines.append(f'    唯一值数: {best["unique_count"]} [置信度: {conf}]')
        lines.append('')

    lines.append('')
    lines.append('  结构')
    lines.append('  ' + '\u2500' * 58)
    lines.append('')

    hdr_size = result['header_size']
    best_len = result.get('best_length_field')
    best_msgid = result.get('best_msgid_field')
    best_uid = result.get('best_uid_field')

    parts = []
    all_fields = []
    for label, field in [('长度', best_len), ('消息ID', best_msgid), ('唯一ID', best_uid)]:
        if field:
            all_fields.append((field['offset'], field['offset'] + field['size'] - 1, field['type'], label))
    all_fields.sort(key=lambda x: x[0])
    for start, end, typ, label in all_fields:
        parts.append(f'    [{start}-{end}] {typ}  {label}')
    parts.append(f'    [{hdr_size}-*] 字节  payload')

    for p in parts:
        lines.append(p)

    proto_results = result.get('protobuf_results', [])
    valid_count = sum(1 for r in proto_results if r['valid'])
    lines.append('')
    lines.append('  Protobuf')
    lines.append('  ' + '\u2500' * 58)
    lines.append('')
    if proto_results:
        lines.append(f'    {valid_count}/{len(proto_results)} 个数据包为有效 protobuf')
        for r in proto_results:
            status = '有效' if r['valid'] else '无效'
            lines.append(f'    #{r["packet"]}: {status}')
        if valid_count > 0 and valid_count == len(proto_results):
            lines.append('')
            lines.append(f'    Payload 是完全有效的 protobuf -- 使用 bbpb decode 查看')
    else:
        lines.append('    （无 payload 可分析）')

    return '\n'.join(lines) + '\n'


def format_json(result):
    # type: (Dict) -> str
    serializable = {
        'endian': result['endian'],
        'packet_count': result['packet_count'],
        'packets': [
            {k: list(v) if k == 'raw' else v for k, v in p.items()}
            for p in result['packets']
        ],
        'byte_mask': result['byte_mask'],
        'length_candidates': result['length_candidates'],
        'best_length_field': result['best_length_field'],
        'msgid_candidates': result['msgid_candidates'],
        'best_msgid_field': result['best_msgid_field'],
        'uid_candidates': result['uid_candidates'],
        'best_uid_field': result['best_uid_field'],
        'header_size': result['header_size'],
        'valid_protobuf_count': sum(1 for r in result.get('protobuf_results', []) if r['valid']),
        'protobuf_valid': all(r['valid'] for r in result.get('protobuf_results', [])),
    }
    return json.dumps(serializable, indent=2, ensure_ascii=False, default=str)
