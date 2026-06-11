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

import math
from hypothesis import given
import hypothesis.strategies as st
import strategies

from bbpbcn.lib.types import fixed


# 逆运算检查。确保 bbp 编码的值解码后得到相同的值
@given(x=strategies.input_map["fixed32"])
def test_fixed32_inverse(x):
    encoded = fixed.encode_fixed32(x)
    decoded, pos = fixed.decode_fixed32(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=st.binary(min_size=4))
def test_fixed32_idem(x):
    try:
        value, pos = fixed.decode_fixed32(x, 0)
    except DecoderException:
        assume(True)
        return

    encoded = fixed.encode_fixed32(value)
    assert encoded == x[:pos]


@given(x=strategies.input_map["sfixed32"])
def test_sfixed32_inverse(x):
    encoded = fixed.encode_sfixed32(x)
    decoded, pos = fixed.decode_sfixed32(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=st.binary(min_size=4))
def test_sfixed32_idem(x):
    try:
        value, pos = fixed.decode_sfixed32(x, 0)
    except DecoderException:
        assume(True)
        return

    encoded = fixed.encode_sfixed32(value)
    assert encoded == x[:pos]


@given(x=strategies.input_map["fixed64"])
def test_fixed64_inverse(x):
    encoded = fixed.encode_fixed64(x)
    decoded, pos = fixed.decode_fixed64(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=st.binary(min_size=8))
def test_fixed64_idem(x):
    try:
        value, pos = fixed.decode_fixed64(x, 0)
    except DecoderException:
        assume(True)
        return

    encoded = fixed.encode_fixed64(value)
    assert encoded == x[:pos]


@given(x=strategies.input_map["sfixed64"])
def test_sfixed64_inverse(x):
    encoded = fixed.encode_sfixed64(x)
    decoded, pos = fixed.decode_sfixed64(encoded, 0)
    assert pos == len(encoded)
    assert decoded == x


@given(x=st.binary(min_size=8))
def test_sfixed64_idem(x):
    try:
        value, pos = fixed.decode_sfixed64(x, 0)
    except DecoderException:
        assume(True)
        return

    encoded = fixed.encode_sfixed64(value)
    assert encoded == x[:pos]


@given(x=strategies.input_map["float"])
def test_float_inverse(x):
    encoded = fixed.encode_float(x)
    decoded, pos = fixed.decode_float(encoded, 0)
    assert pos == len(encoded)
    if math.isnan(x):
        assert math.isnan(decoded)
    else:
        assert decoded == x


# 虽然测试 float_idem 不错，但它不是默认类型，所以可能没问题
# 对 float 进行解码再编码得到相同结果可能有问题
# @given(x=st.binary(min_size=4))
# def test_float_idem(x):
#    try:
#        value, pos = fixed.decode_float(x, 0)
#    except DecoderException:
#        assume(True)
#        return
#
#    encoded = fixed.encode_float(value)
#    assert encoded == x[:pos]


@given(x=strategies.input_map["double"])
def test_double_inverse(x):
    encoded = fixed.encode_double(x)
    decoded, pos = fixed.decode_double(encoded, 0)
    assert pos == len(encoded)
    if math.isnan(x):
        assert math.isnan(decoded)
    else:
        assert decoded == x


# @given(x=st.binary(min_size=8))
# def test_double_idem(x):
#    try:
#        value, pos = fixed.decode_double(x, 0)
#    except DecoderException:
#        assume(True)
#        return
#
#    encoded = fixed.encode_double(value)
#    assert encoded == x[:pos]
