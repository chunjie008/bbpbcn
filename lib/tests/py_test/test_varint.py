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

from hypothesis import given, example, note, assume
import hypothesis.strategies as st
import strategies
import pytest
import six

from google.protobuf.internal import wire_format, encoder, decoder

from bbpb_cn.lib.types import varint
from bbpb_cn.lib.exceptions import EncoderException, DecoderException


# 测试对于任意给定字节，以 varint 解码时不会改变它们
@given(x=st.binary(max_size=10))
@example(x=b"\x80\x01")
@example(x=b"\x80\x81")
@example(x=b"\x81\x80\x80\x80\x80\x80\x80\x80\x01\x00")
@example(x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x00")
@example(x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x80")
def test_varint_idem_uvarint(x):
    try:
        decoded, pos = varint.decode_uvarint(x, 0)
    except DecoderException:
        assume(True)
        return

    encoded = varint.encode_uvarint(decoded)
    assert encoded == x[:pos]


# 测试对于任意给定字节，以 varint 解码时不会改变它们
@given(x=st.binary(min_size=10, max_size=10))
@example(x=b"\x80\x01")
@example(x=b"\x80\x81")
@example(x=b"\x81\x80\x80\x80\x80\x80\x80\x80\x01\x00")
@example(x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x00")
@example(x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x80")
@example(x=b"\x8d\x9b\xb0\xcc\xcf\xdc\xea\xf4\xf9\x02")
def test_varint_idem_varint(x):
    try:
        decoded, pos = varint.decode_varint(x, 0)
    except DecoderException:
        assume(True)
        return
    encoded = varint.encode_varint(decoded)
    assert encoded == x[:pos]


# 测试对于任意给定字节，以 varint 解码时不会改变它们
@given(x=st.binary(max_size=10))
@example(x=b"\x80\x01")
@example(x=b"\x80\x81")
@example(x=b"\x81\x80\x80\x80\x80\x80\x80\x80\x01\x00")
@example(x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x00")
@example(
    x=b"\x80\x80\x80\x80\x80\x80\x80\x80\x81\x80"
)  # 我认为这个在解码时会溢出并被截断
def test_varint_idem_svarint(x):
    try:
        decoded, pos = varint.decode_svarint(x, 0)
    except DecoderException:
        assume(True)
        return
    encoded = varint.encode_svarint(decoded)
    assert encoded == x[:pos]


# 逆运算检查。确保 bbp 编码的值解码后得到相同的值
@given(x=strategies.input_map["uint"])
@example(x=18446744073709551615)
def test_uvarint_inverse(x):
    encoded = varint.encode_uvarint(x)
    decoded, pos = varint.decode_uvarint(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=strategies.input_map["int"])
@example(x=-1143843382522404608)
@example(x=-1)
@example(x=8784740448578833805)
def test_varint_inverse(x):
    encoded = varint.encode_varint(x)
    decoded, pos = varint.decode_varint(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=strategies.input_map["sint"])
def test_svarint_inverse(x):
    encoded = varint.encode_svarint(x)
    decoded, pos = varint.decode_svarint(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=st.integers(min_value=varint.MAX_UVARINT + 1))
def test_bounds_varints(x):
    with pytest.raises(EncoderException):
        varint.encode_uvarint(x)

    with pytest.raises(EncoderException):
        varint.encode_uvarint(-x)

    with pytest.raises(EncoderException):
        varint.encode_varint(x)

    with pytest.raises(EncoderException):
        varint.encode_varint(-x)

    with pytest.raises(EncoderException):
        varint.encode_svarint(x)

    with pytest.raises(EncoderException):
        varint.encode_svarint(-x)


def _gen_append_bytearray(arr):
    def _append_bytearray(x):
        if isinstance(x, (str, int)):
            arr.append(x)
        elif isinstance(x, bytes):
            arr.extend(x)
        else:
            raise EncoderException("protobuf 库返回了未知类型")

    return _append_bytearray


# 针对 google 的 varint 函数测试我们的
@given(x=strategies.input_map["uint"])
def test_uvarint_encode(x):
    encoded_google = bytearray()
    encoder._EncodeVarint(_gen_append_bytearray(encoded_google), x)
    encoded_bbpb = varint.encode_uvarint(x)
    assert encoded_google == encoded_bbpb


@given(x=strategies.input_map["uint"])
def test_uvarint_decode(x):
    buf = bytearray()
    encoder._EncodeVarint(_gen_append_bytearray(buf), x)

    if six.PY2:
        buf = str(buf)
    decoded_google, _ = decoder._DecodeVarint(buf, 0)
    decoded_bbpb, _ = varint.decode_uvarint(buf, 0)
    assert decoded_google == decoded_bbpb


@given(x=strategies.input_map["int"])
def test_varint_encode(x):
    encoded_google = bytearray()
    encoder._EncodeSignedVarint(_gen_append_bytearray(encoded_google), x)
    encoded_bbpb = varint.encode_varint(x)
    assert encoded_google == encoded_bbpb


@given(x=strategies.input_map["int"])
def test_varint_decode(x):
    buf = bytearray()
    encoder._EncodeSignedVarint(_gen_append_bytearray(buf), x)

    if six.PY2:
        buf = bytes(buf)
    decoded_google, _ = decoder._DecodeSignedVarint(buf, 0)
    decoded_bbpb, _ = varint.decode_varint(buf, 0)
    assert decoded_google == decoded_bbpb


@given(x=strategies.input_map["sint"])
def test_svarint_encode(x):
    encoded_google = bytearray()
    encoder._EncodeSignedVarint(
        _gen_append_bytearray(encoded_google), wire_format.ZigZagEncode(x)
    )
    encoded_bbpb = varint.encode_svarint(x)
    assert encoded_google == encoded_bbpb


@given(x=strategies.input_map["sint"])
@example(x=-1)
def test_svarint_decode(x):
    buf = bytearray()
    encoder._EncodeSignedVarint(_gen_append_bytearray(buf), wire_format.ZigZagEncode(x))

    if six.PY2:
        buf = bytes(buf)
    decoded_google_uint, _ = decoder._DecodeVarint(buf, 0)
    decoded_google = wire_format.ZigZagDecode(decoded_google_uint)
    decoded_bbpb, _ = varint.decode_svarint(buf, 0)

    assert decoded_google == decoded_bbpb
