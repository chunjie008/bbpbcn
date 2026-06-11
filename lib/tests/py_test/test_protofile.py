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

import os
import sys
import six
import math
import glob
import shutil
import base64
import struct
import pytest
import logging
import tempfile
import subprocess
import hypothesis
from hypothesis import given, assume, note, settings, HealthCheck
import hypothesis.strategies as st
import google.protobuf.json_format
import strategies
import bbpbcn.lib
import bbpbcn.lib.protofile as protofile
from bbpbcn.lib.types import length_delim
from bbpbcn.lib.config import Config
from bbpbcn.lib.typedef import TypeDef


to_suppress = []
if six.PY3:
    to_suppress = (HealthCheck.function_scoped_fixture,)


@given(
    typedef=strategies.message_typedef_gen(named_fields=False),
    name=st.from_regex(protofile.NAME_REGEX),
)
@settings(suppress_health_check=to_suppress)
def test_proto_export(tmp_path, typedef, name):
    """检查我们生成的 proto 文件不会抛出错误"""
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(tmp_path), suffix=".proto", delete=True
    ) as outfile:
        typedef_map = {name: typedef}

        note(typedef_map)

        # 先尝试导出为字符串
        protofile.export_proto(typedef_map)

        protofile.export_proto(typedef_map, output_file=outfile)

        py_out = str(tmp_path / "py_out")
        if os.path.exists(py_out):
            shutil.rmtree(py_out)
        os.mkdir(py_out)
        outfile.flush()
        subprocess.check_call(
            "/usr/bin/protoc --python_out ./py_out %s" % os.path.basename(outfile.name),
            shell=True,
            cwd=str(tmp_path),
        )


@given(
    x=strategies.gen_message(named_fields=False),
    name=st.from_regex(protofile.NAME_REGEX),
)
@settings(suppress_health_check=to_suppress)
def test_proto_export_inverse(tmp_path, x, name):
    """生成一个 proto 文件并尝试重新导入。这并不涵盖
    我们想要尝试导入的所有可能的 proto 文件"""
    config = Config()
    typedef, message = x
    name = six.ensure_text(name)
    with tempfile.NamedTemporaryFile(
        mode="r+", dir=str(tmp_path), suffix=".proto", delete=True
    ) as outfile:
        typedef_map = {name: typedef}

        protofile.export_proto(typedef_map, output_file=outfile)
        outfile.flush()

        outfile.seek(0)
        new_typedef_map = protofile.import_proto(config, input_file=outfile)

        config.known_types.update(new_typedef_map)
        # 验证
        for name, typedef in new_typedef_map.items():
            bbpbcn.validate_typedef(typedef, config=config)

        def _check_field_types(typedef1, typedef2):
            for field_num in typedef1.keys():
                # 确保不会丢失键
                assert field_num in typedef2
                assert typedef1[field_num]["type"] == typedef2[field_num]["type"]
                if typedef1[field_num]["type"] == "message":
                    message_typedef1 = None
                    message_typedef2 = None
                    if "message_typedef" in typedef1[field_num]:
                        message_typedef1 = typedef1[field_num]["message_typedef"]
                    elif "message_type_name" in typedef1[field_num]:
                        assert typedef1[field_num]["message_type_name"] in typedef_map
                        message_typedef1 = typedef_map[
                            typedef1[field_num]["message_type_name"]
                        ]
                    if "message_typedef" in typedef2[field_num]:
                        message_typedef2 = typedef2[field_num]["message_typedef"]
                    elif "message_type_name" in typedef2[field_num]:
                        assert (
                            typedef2[field_num]["message_type_name"] in new_typedef_map
                        )
                        message_typedef2 = new_typedef_map[
                            typedef2[field_num]["message_type_name"]
                        ]

                    _check_field_types(message_typedef1, message_typedef2)

        note(typedef_map)
        note(new_typedef_map)
        for name, typedef in typedef_map.items():
            _check_field_types(typedef, new_typedef_map[name])

        note(new_typedef_map[name])
        # 尝试使用 typedef 实际编码一条消息
        encode_forward = length_delim.encode_message(
            message, config, TypeDef.from_dict(typedef_map[name])
        )

        config.known_types = new_typedef_map
        encode_backward = length_delim.encode_message(
            message, config, TypeDef.from_dict(new_typedef_map[name])
        )

        decode_forward, _, _, _ = length_delim.decode_message(
            encode_forward, config, TypeDef.from_dict(new_typedef_map[name])
        )
        decode_backward, _, _, _ = length_delim.decode_message(
            encode_backward, config, TypeDef.from_dict(typedef_map[name])
        )


@pytest.mark.filterwarnings("ignore:调用已弃用的 create 函数.*")
def test_proto_import_examples():
    config = Config()
    # 尝试导入所有从 protobuf 仓库中提取的示例
    protofiles = glob.glob("tests/deps/protobuf/src/google/protobuf/*.proto")
    # 以下文件包含我们不支持的某些机制，主要是导入
    unsupported_files = {
        "tests/deps/protobuf/src/google/protobuf/api.proto",  # 导入
        "tests/deps/protobuf/src/google/protobuf/unittest_optimize_for.proto",  # 导入
        "tests/deps/protobuf/src/google/protobuf/type.proto",  # 导入
        "tests/deps/protobuf/src/google/protobuf/unittest_lite_imports_nonlite.proto",  # 导入
        "tests/deps/protobuf/src/google/protobuf/unittest_lite.proto",  # 不支持 group 类型
        "tests/deps/protobuf/src/google/protobuf/unittest_embed_optimize_for.proto",  # 导入
        "tests/deps/protobuf/src/google/protobuf/unittest.proto",  # group
        "tests/deps/protobuf/src/google/protobuf/unittest_lazy_dependencies.proto",  # 导入
    }
    assert len(protofiles) != 0
    for target_file in protofiles:
        if target_file in unsupported_files:
            print("跳过文件: %s" % target_file)
            continue

        print("测试文件: %s" % target_file)
        typedef_map_out = protofile.import_proto(config, input_filename=target_file)
        config.known_types = typedef_map_out
        for name, typedef in typedef_map_out.items():
            logging.debug("已知消息: %s" % config.known_types)
            bbpbcn.lib.validate_typedef(typedef, config=config)


@given(
    x=strategies.gen_message(named_fields=False),
    name=st.from_regex(protofile.NAME_REGEX),
)
@settings(suppress_health_check=to_suppress)
@pytest.mark.filterwarnings("ignore:调用已弃用的 create 函数.*")
def test_proto_decode(tmp_path, x, name):
    config = Config()
    typedef, message = x
    """导出为 protobuf 并尝试解码我们用其编码的消息"""
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(tmp_path), suffix=".proto", delete=True
    ) as outfile:
        typedef_map = {name: typedef}

        encoded_message = length_delim.encode_message(
            message, config, TypeDef.from_dict(typedef)
        )

        note(typedef_map)
        basename = os.path.basename(outfile.name)

        # 导出 protobuf 文件并编译
        protofile.export_proto(typedef_map, output_file=outfile, package=basename[:-6])

        py_out = str(tmp_path / "py_out")
        if os.path.exists(py_out):
            shutil.rmtree(py_out)
        os.mkdir(py_out)
        outfile.flush()
        subprocess.check_call(
            "/usr/bin/protoc --python_out ./py_out %s" % basename,
            shell=True,
            cwd=str(tmp_path),
        )

        # 尝试导入文件
        sys.path.insert(0, str(tmp_path) + "/py_out/")
        # 去掉 .proto 后缀
        try:
            proto_module = __import__(basename[:-6] + "_pb2")
            del sys.path[0]
        except SyntaxError:
            logging.debug("捕获到 protoc 导入的语法错误")
            return

        message_class = getattr(proto_module, name)

        note(encoded_message)
        my_message = message_class()
        my_message.ParseFromString(encoded_message)

        decoded_message = google.protobuf.json_format.MessageToDict(
            my_message, including_default_value_fields=True
        )

        note(message)
        note(decoded_message)
        note(
            google.protobuf.json_format.MessageToJson(
                my_message, including_default_value_fields=True
            )
        )

        def _check_field_match(orig_value, new_value):
            note(type(new_value))
            note(type(orig_value))
            if isinstance(orig_value, six.integer_types) and isinstance(new_value, str):
                assert str(orig_value) == new_value
            elif isinstance(orig_value, bytes):
                assert orig_value == base64.b64decode(new_value)
            elif isinstance(new_value, dict):
                _check_message_match(orig_value, new_value)
            elif isinstance(orig_value, float):
                # 标准化浮点数
                if isinstance(new_value, str):
                    if "Infinity" in new_value:
                        assert math.isinf(orig_value)
                    else:
                        assert new_value == "NaN"
                        assert math.isnan(new_value)

                else:
                    # 打包和解包浮点数以尝试标准化
                    try:
                        orig_value_packed = struct.pack("<f", orig_value)
                        (orig_value,) = struct.unpack("<f", orig_value_packed)
                        new_value_packed = struct.pack("<f", orig_value)
                        (new_value,) = struct.unpack("<f", orig_value_packed)
                        assert orig_value == new_value
                    except OverflowError:
                        orig_value_packed = struct.pack("<d", orig_value)
                        (orig_value,) = struct.unpack("<d", orig_value_packed)
                        new_value_packed = struct.pack("<d", new_value)
                        (new_value,) = struct.unpack("<d", new_value_packed)
                        assert orig_value == new_value

            else:
                assert orig_value == new_value

        def _check_message_match(message_orig, message_new):
            for field_key, field_value in message_new.items():
                if field_key.startswith("field"):
                    field_key = field_key[5:]
                orig_value = message_orig[field_key]
                if isinstance(field_value, list):
                    if not isinstance(orig_value, list):
                        orig_value = [orig_value]
                    assert len(orig_value) == len(field_value)
                    for orig_value, new_value in zip(orig_value, field_value):
                        _check_field_match(orig_value, new_value)
                else:
                    _check_field_match(orig_value, field_value)

        # 检查所有字段是否匹配
        _check_message_match(message, decoded_message)
