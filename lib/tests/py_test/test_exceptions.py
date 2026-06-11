"""尝试测试库生成的异常。所有异常都应抛出某种形式的 bbpbcnException。"""

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

from hypothesis import given
import hypothesis.strategies as st

from bbpbcn.lib import config
from bbpbcn.lib.types import fixed, varint, length_delim
from bbpbcn.lib.exceptions import (
    bbpbcnException,
    DecoderException,
    EncoderException,
)

# 固定类型异常测试


## 编码
@given(value=st.integers())
def test_encode_fixed32(value):
    try:
        fixed.encode_fixed32(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.integers())
def test_encode_sfixed32(value):
    try:
        fixed.encode_sfixed32(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.decimals())
def test_encode_float(value):
    try:
        fixed.encode_float(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.integers())
def test_encode_fixed64(value):
    try:
        fixed.encode_fixed64(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.integers())
def test_encode_sfixed64(value):
    try:
        fixed.encode_sfixed64(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.decimals())
def test_encode_double(value):
    try:
        fixed.encode_double(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


## 解码


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_fixed32(buf, pos):
    try:
        fixed.decode_fixed32(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_sfixed32(buf, pos):
    try:
        fixed.decode_sfixed32(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_float(buf, pos):
    try:
        fixed.decode_float(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_fixed64(buf, pos):
    try:
        fixed.decode_fixed64(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_sfixed64(buf, pos):
    try:
        fixed.decode_sfixed64(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=100), pos=st.integers(max_value=200))
def test_decode_double(buf, pos):
    try:
        fixed.decode_double(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


# Varint 异常测试
@given(value=st.integers())
def test_encode_uvarint(value):
    try:
        varint.encode_uvarint(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.integers())
def test_encode_varint(value):
    try:
        varint.encode_varint(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.integers())
def test_encode_svarint(value):
    try:
        varint.encode_svarint(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(buf=st.binary(max_size=32), pos=st.integers(max_value=64))
def test_decode_uvarint(buf, pos):
    try:
        varint.decode_uvarint(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=32), pos=st.integers(max_value=64))
def test_decode_varint(buf, pos):
    try:
        varint.decode_varint(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary(max_size=32), pos=st.integers(max_value=64))
def test_decode_svarint(buf, pos):
    try:
        varint.decode_svarint(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


# length_delim 异常测试


@given(value=st.binary())
def encode_bytes(value):
    try:
        length_delim.encode_bytes(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(value=st.binary(), pos=st.integers(max_value=2000))
def test_decode_bytes(value, pos):
    try:
        length_delim.decode_bytes(value, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(value=st.binary())
def test_encode_bytes_hex(value):
    try:
        length_delim.encode_bytes_hex(value)
    except bbpbcnException as exc:
        assert not isinstance(exc, DecoderException)
        pass


@given(buf=st.binary(), pos=st.integers(max_value=2000))
def test_decode_bytes_hex(buf, pos):
    try:
        length_delim.decode_bytes_hex(buf, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(value=st.binary(), pos=st.integers(max_value=2000))
def test_decode_string(value, pos):
    try:
        length_delim.decode_string(value, pos)
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary())
def test_decode_message(buf):
    try:
        length_delim.decode_message(buf, config.Config())
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass


@given(buf=st.binary())
def test_decode_lendelim_message(buf):
    try:
        length_delim.decode_lendelim_message(buf, config.Config())
    except bbpbcnException as exc:
        assert not isinstance(exc, EncoderException)
        pass
