import struct
import binascii
import json

TYPE_MAP = {
    'int8': ('<b', 1, 'int'),
    'uint8': ('<B', 1, 'int'),
    'int16_le': ('<h', 2, 'int'),
    'uint16_le': ('<H', 2, 'int'),
    'int16_be': ('>h', 2, 'int'),
    'uint16_be': ('>H', 2, 'int'),
    'int24_le': ('<i', 3, 'int'),
    'uint24_le': ('<I', 3, 'int'),
    'int24_be': ('>i', 3, 'int'),
    'uint24_be': ('>I', 3, 'int'),
    'int32_le': ('<i', 4, 'int'),
    'uint32_le': ('<I', 4, 'int'),
    'int32_be': ('>i', 4, 'int'),
    'uint32_be': ('>I', 4, 'int'),
    'int64_le': ('<q', 8, 'int'),
    'uint64_le': ('<Q', 8, 'int'),
    'int64_be': ('>q', 8, 'int'),
    'uint64_be': ('>Q', 8, 'int'),
    'float_le': ('<f', 4, 'float'),
    'float_be': ('>f', 4, 'float'),
    'double_le': ('<d', 8, 'float'),
    'double_be': ('>d', 8, 'float'),
}

PADDED_TYPES = {'int24_le', 'uint24_le', 'int24_be', 'uint24_be'}
PADDED_FORMATS = {
    'int24_le': '<i', 'uint24_le': '<I',
    'int24_be': '>i', 'uint24_be': '>I',
}

def _parse_hex(hex_str):
    hex_str = hex_str.strip()
    if hex_str.startswith('0x') or hex_str.startswith('0X'):
        hex_str = hex_str[2:]
    hex_str = hex_str.replace(' ', '').replace('-', '').replace(':', '').replace('\t', '')
    return binascii.unhexlify(hex_str)


def _convert_single(hex_str, target_type):
    raw = _parse_hex(hex_str)

    if target_type in TYPE_MAP:
        fmt, size, _ = TYPE_MAP[target_type]
        if len(raw) < size:
            raise ValueError(
                'hex too short for %s: need %d byte(s), got %d' % (target_type, size, len(raw))
            )
        if target_type in PADDED_TYPES:
            raw3 = raw[:3]
            if 'be' in target_type:
                padded = b'\x00' + raw3
            else:
                padded = raw3 + b'\x00'
            return struct.unpack(PADDED_FORMATS[target_type], padded)[0]
        return struct.unpack(fmt, raw[:size])[0]
    elif target_type == 'string':
        return raw.decode('utf-8', errors='replace')
    elif target_type == 'hex_raw':
        return raw.hex()
    elif target_type == 'bits':
        return ' '.join(format(b, '08b') for b in raw)
    else:
        raise ValueError('unknown type: %s' % target_type)


def convert_hex(hex_str, target_type):
    return _convert_single(hex_str, target_type)


def convert_hex_lines(lines, target_type, json_output=False):
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            value = _convert_single(line, target_type)
            results.append({'hex': line, 'type': target_type, 'value': value})
        except (ValueError, binascii.Error) as e:
            results.append({'hex': line, 'type': target_type, 'error': str(e)})

    if json_output:
        return json.dumps(results, indent=2, ensure_ascii=False, default=str)
    else:
        out_lines = []
        for r in results:
            if 'error' in r:
                out_lines.append('error: %s (hex: %s)' % (r['error'], r['hex']))
            else:
                out_lines.append(str(r['value']))
        return '\n'.join(out_lines)
