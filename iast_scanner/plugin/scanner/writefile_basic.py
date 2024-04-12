#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Copyright 2017-2020 Baidu Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from core.components.plugin import scan_plugin_base


class ScanPlugin(scan_plugin_base.ScanPluginBase):

    plugin_info = {
        "name": "writefile_basic",
        "show_name": "任意文件写入检测插件",
        "description": "基础任意文件写入漏洞检测插件"
    }

    def mutant(self, rasp_result_ins):
        """
        测试向量生成
        """
        if not rasp_result_ins.has_hook_type("writeFile"):
            return

        linux_payload_list = [
            ("../../../../../../../../../../../../../../../../../tmp/opeanrasp.test",
             "/tmp/opeanrasp.test"),
            ("../../../tmp/rasp", "/tmp/rasp"),
            ("../../../../../../tmp/opeanrasp.test", "/tmp/opeanrasp.test")
        ]

        windows_payload_list = [
            ("..\\..\\..\\..\\..\\..\\..\\..\\..\\opeanrasp.test", ":\\opeanrasp.test"),
            ("..\\..\\..\\opeanrasp.test", ":\\opeanrasp.test"),
            ("file://c:\\opeanrasp.test", "c:\\opeanrasp.test")
        ]

        server_os = rasp_result_ins.get_server_info()["os"]
        if server_os == "Windows":
            payload_list = windows_payload_list
        else:
            payload_list = linux_payload_list

        # 获取所有待测试参数
        request_data_ins = self.new_request_data(rasp_result_ins)
        test_params = self.mutant_helper.get_params_list(
            request_data_ins, ["get", "post", "json", "headers", "cookies"])

        for param in test_params:
            if not request_data_ins.is_param_concat_in_hook("writeFile", param["value"]):
                continue
            payload_seq = self.gen_payload_seq()
            for payload in payload_list:
                request_data_ins = self.new_request_data(rasp_result_ins, payload_seq, payload[1])
                request_data_ins.set_param(param["type"], param["name"], payload[0])

                hook_filter = [{
                    "type": "writeFile",
                    "filter": {
                        "realpath": payload[1]
                    }
                }]
                request_data_ins.set_filter(hook_filter)
                request_data_list = [request_data_ins]
                yield request_data_list

    def check(self, request_data_list):
        """
        请求结果检测
        """
        request_data_ins = request_data_list[0]
        feature = request_data_ins.get_payload_info()["feature"]
        rasp_result_ins = request_data_ins.get_rasp_result()
        if rasp_result_ins is None:
            return None
        if self.checker.check_concat_in_hook(rasp_result_ins, "writeFile", feature):
            return "写入文件的路径可被用户控制"
        else:
            return None
