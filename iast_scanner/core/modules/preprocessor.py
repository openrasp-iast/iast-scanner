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

import os
import lru
import sys
import zlib
import time
import asyncio
import logging
import aiohttp
import tornado.web
import tornado.ioloop
import tornado.httpserver
import multiprocessing

from core.modules import base
from core.model import new_request_model
from core.components import exceptions
from core.components import rasp_result
from core.components.logger import Logger
from core.components.config import Config
from core.components.plugin import dedup_plugin_base
from core.components.communicator import Communicator


class Preprocessor(base.BaseModule):

    def __init__(self):

        # 初始化插件
        plugin_path = "plugin.deduplicate"
        plugin_name = Config().get_config("preprocessor.plugin_name")
        try:
            plugin_module = __import__(plugin_path, fromlist=[plugin_name])
            self.dedup_plugin = getattr(
                plugin_module, plugin_name).DedupPlugin()
            assert isinstance(self.dedup_plugin,
                              dedup_plugin_base.DedupPluginBase)
        except Exception as e:
            Logger().warning("Dedupulicate plugin {} init fail!".format(plugin_name), exc_info=e)

        self.dedup_lru = DedupLru(Config().get_config("preprocessor.request_lru_size"))
        self.new_request_storage = ResultStorage(self.dedup_lru)
        self.app = tornado.web.Application([
            tornado.web.url(
                Config().get_config("preprocessor.api_path"),
                jsonHandler,
                dict(
                    dedup_lru=self.dedup_lru,
                    dedup_plugin=self.dedup_plugin,
                    new_request_storage=self.new_request_storage,
                )
            )
        ])

    def run(self):
        """
        启动http server
        """
        server = tornado.httpserver.HTTPServer(
            self.app, max_buffer_size=Config().get_config("preprocessor.max_buffer_size"))
        try:
            server.bind(Config().get_config("preprocessor.http_port"))
        except OSError as e:
            Logger().critical("Preprocessor bind port error!", exc_info=e)
            sys.exit(1)
        else:
            # 这里会创建多个子进程，需要重新初始化Communicator
            server.start(Config().get_config("preprocessor.process_num"))
            Communicator().init_new_module(type(self).__name__)
            # 记录pid
            while True:
                if Communicator().set_pre_http_pid(os.getpid()):
                    break
                else:
                    pids = ", ".join(str(x) for x in Communicator().get_pre_http_pid())
                    Logger().error("Preprocessor HTTP Server set pid failed! Running pids: {}".format(pids))
                    time.sleep(3)
            tornado.ioloop.IOLoop.current().start()


class jsonHandler(tornado.web.RequestHandler):
    """
    处理httpServer收到的json
    """

    def initialize(self, dedup_lru, dedup_plugin, new_request_storage):
        """
        初始化
        """
        self.dedup_lru = dedup_lru
        self.dedup_plugin = dedup_plugin
        self.new_request_storage = new_request_storage

    def get(self):
        """
        处理GET请求
        """
        msg = """
        OpenRASP IAST Server is running ... </br>\n
        This interface is used by the OpenRASP Agent to communicate with IAST, and should not be accessed with browser...
        """
        self.write(msg)

    async def post(self):
        """
        处理POST请求
        """
        try:
            data = self.request.body
            headers = self.request.headers
            content_type = self.request.headers.get("Content-Type", "None")
            if not content_type.startswith("application/json"):
                raise exceptions.ContentTypeInvalid
            content_encoding = self.request.headers.get("Content-Encoding", "None")
            if content_encoding == "deflate":
                try:
                    data = zlib.decompress(data)
                except Exception as e:
                    Logger().warning("Deflated data decode error!", exc_info=e)
                    raise exceptions.ContentTypeInvalid
            rasp_result_ins = rasp_result.RaspResult(data)
            Logger().info("Received request data: " + str(rasp_result_ins))
            if rasp_result_ins.is_scan_result():
                self.send_data(rasp_result_ins)
            else:
                await self.dedup_data(rasp_result_ins)
            self.write('{"status": 0, "msg":"ok"}\n')
        except exceptions.OriExpectedException as e:
            self.write('{"status": 1, "msg":"data invalid"}\n')
            Communicator().increase_value("invalid_data")
            Logger().warning("Invalid data: {} posted to http server, rejected!".format(data))
        except Exception as e:
            Logger().error(
                "Unexpected error occured when process data:{}".format(data), exc_info=e)
            self.send_error(500)
        return

    async def dedup_data(self, rasp_result_ins):
        """
        对非扫描请求new_request_data进行去重

        Parameters:
            rasp_result_ins - 待去重的RaspResult实例

        Raises:
            exceptions.DatabaseError - 插入数据失败抛出此异常

        """
        self.update_setting()
        hash_str = self.dedup_plugin.get_hash(rasp_result_ins)
        if hash_str is None:
            Logger().debug("Drop white list request with request_id: {}".format(
                rasp_result_ins.get_request_id()))
            Communicator().increase_value("duplicate_request")
        else:
            host_port = rasp_result_ins.get_host_port()
            try:
                self.dedup_lru.check(host_port, hash_str)
                Logger().info("Drop duplicate request with request_id: {} (request in lru)".format(
                    rasp_result_ins.get_request_id()))
                Communicator().increase_value("duplicate_request")
            except KeyError:
                rasp_result_ins.set_hash(hash_str)
                try:
                    data_stored = await self.new_request_storage.put(rasp_result_ins)
                except exceptions.DatabaseError as e:
                    self.dedup_lru.delete_key(host_port, hash_str)
                    raise e
                else:
                    if data_stored:
                        Logger().info("Get new request with request_id: {}".format(
                            rasp_result_ins.get_request_id()))
                        Communicator().increase_value("new_request")
                    else:
                        Logger().info("Drop duplicate request with request_id: {}".format(
                            rasp_result_ins.get_request_id()))
                        Communicator().increase_value("duplicate_request")

    def send_data(self, rasp_result_ins):
        """
        向rasp_result_queue发送RaspResult实例

        Parameters:
            rasp_result_ins - 待发送的RaspResult实例
        """
        queue_name = "rasp_result_queue_" + \
            str(rasp_result_ins.get_result_queue_id())
        Logger().info("Send scan request data with id:{} to queue:{}".format(
            rasp_result_ins.get_request_id(), queue_name))
        Communicator().send_data(queue_name, rasp_result_ins)
        Communicator().increase_value("rasp_result_request")

    def update_setting(self):
        """
        检查并更新运行时配置
        """
        action = Communicator().get_preprocessor_action()
        if action is not None:
            # 执行清空lru的action
            for host_port in action["lru_clean"]:
                self.new_request_storage.reset(host_port)
                self.dedup_lru.clean_lru(host_port)


class ResultStorage(object):

    def __init__(self, dedup_lru):
        """
        初始化
        """
        self.models = {}
        self.dedup_lru = dedup_lru

    def _get_model(self, host_port):
        """
        获取NewRequestModel实例，不存在则创建并缓存

        Parameters:
            host_port - host + "_" + str(port) 组成的字符串, 指定获取的表名

        Returns:
            获取到的NewRequestModel实例
        """
        now_time = time.time()
        if host_port not in self.models or self.models[host_port][1] < now_time:

            del_host = []
            for host_port_item, model in self.models.items():
                if model[1] < now_time:
                    del_host.append(host_port_item)

            for host_port_item in del_host:
                del self.models[host_port_item]
                self.dedup_lru.clean_lru(host_port_item)

            self.models[host_port] = [
                new_request_model.NewRequestModel(host_port, multiplexing_conn=False),
                time.time() + 180
            ]

        return self.models[host_port][0]

    def reset(self, host_port):
        """
        清除缓存的NewRequestModel实例

        Parameters:
            host_port - host + "_" + str(port) 组成的字符串, 指定清除的实例的表名
        """
        if host_port in self.models:
            del self.models[host_port]

    async def put(self, rasp_result_ins):
        """
        将RaspResult实例插入对应的数据表

        Parameters:
            rasp_result_ins - 插入的RaspResult实例
        """
        host_port = rasp_result_ins.get_host_port()
        model = self._get_model(host_port)
        return await model.put(rasp_result_ins)


class DedupLru(object):
    """
    非扫描请求入库前的去重LRU集合
    """

    def __init__(self, max_size):
        """
        初始化
        """
        self.lru_dict = {}
        self.max_size = max_size

    def check(self, host_port, key):
        """
        判断key是否存在于lru中，不存在则加入

        Parameters:
            host_port - host + "_" + str(port) 组成的字符串，指定查找的LRU
            key - 在LRU中查找的key

        Raises:
            KeyError - key不存在于LRU中
        """
        try:
            target_lru = self.lru_dict[host_port]
        except KeyError:
            self.lru_dict[host_port] = lru.LRU(self.max_size)
            self.lru_dict[host_port][key] = None
            raise KeyError

        try:
            target_lru[key]
        except KeyError:
            target_lru[key] = None
            raise KeyError

    def delete_key(self, host_port, key):
        """
        在LRU中删除指定的key

        Parameters:
            host_port - host + "_" + str(port) 组成的字符串，指定删除的key所在的LRU
            key - 在LRU中删除的key

        """
        try:
            target_lru = self.lru_dict[host_port]
            del target_lru[key]
        except KeyError:
            pass

    def clean_lru(self, host_port):
        """
        清空LRU

        Parameters:
            host_port - host + "_" + str(port) 组成的字符串，指定清空的LRU
        """
        self.lru_dict.pop(host_port, None)
