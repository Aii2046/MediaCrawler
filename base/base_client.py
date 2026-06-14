# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import json
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page

from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils
from tools.httpx_util import make_async_client

if TYPE_CHECKING:
    from proxy.proxy_ip_pool import ProxyIpPool


class BasePlatformClient(AbstractApiClient, ProxyRefreshMixin):
    """
    所有平台 Client 的公共基类。

    封装了通用的：
    - 构造函数（代理、超时、请求头、cookie 等）
    - request() 模板方法（代理刷新 → httpx 请求 → 委托子类解析响应）
    - update_cookies()（从浏览器上下文更新 cookie）
    - _base_get() / _base_post()（无签名的简单 HTTP 请求）
    - download_media()（媒体文件下载）
    - _paginate_comments() / _paginate_creator_posts()（通用分页循环）

    子类只需实现：
    - _parse_response()：解析 JSON + 平台特定错误检查
    - 按需覆盖 get() / post()（如需请求签名）
    - 按需覆盖 request()（如需 retry 装饰器或特殊处理）
    - 平台特有的 API 方法（搜索、评论、创作者等）
    """

    def __init__(
        self,
        timeout: int = 60,
        proxy: Optional[str] = None,
        *,
        headers: Dict[str, str],
        playwright_page: Optional[Page] = None,
        cookie_dict: Optional[Dict[str, str]] = None,
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = ""  # 子类在 __init__ 中覆盖
        self.cookie_urls: List[str] = []  # 子类在 __init__ 中覆盖
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict or {}
        # Initialize proxy pool (from ProxyRefreshMixin)
        self.init_proxy_pool(proxy_ip_pool)

    # ==================== 模板方法 ====================

    async def request(self, method: str, url: str, **kwargs) -> Any:
        """
        公共 request 骨架：代理刷新 → httpx 请求 → 委托子类解析响应。

        子类如需自定义（如 @retry 装饰器、return_response 等），可覆盖此方法。
        """
        await self._refresh_proxy_if_expired()

        return_response = kwargs.pop("return_response", False)
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        if return_response:
            return response.text

        return self._parse_response(response)

    @abstractmethod
    def _parse_response(self, response: httpx.Response) -> Any:
        """
        子类实现：解析 HTTP 响应，进行平台特定的错误检查。

        Args:
            response: httpx 响应对象

        Returns:
            解析后的数据（通常为 Dict）

        Raises:
            平台特定的异常（如 DataFetchError）
        """
        ...

    # ==================== Cookie 管理 ====================

    async def update_cookies(self, browser_context: BrowserContext, urls: Optional[List[str]] = None):
        """
        从浏览器上下文更新 cookie。7 个平台的此方法完全相同。

        注意：ZhihuClient 使用 self.default_headers，需要覆盖此方法。
        """
        cookie_str, cookie_dict = await utils.convert_browser_context_cookies(
            browser_context,
            urls=urls or self.cookie_urls,
        )
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    # ==================== 基础 HTTP 方法 ====================

    async def _base_get(self, uri: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Any:
        """
        无签名的通用 GET 请求。

        子类如需签名（如 XHS、Bilibili、Zhihu），应覆盖 get() 方法，
        但在不需要签名时可直接调用此方法。
        """
        if isinstance(params, dict):
            url = f"{self._host}{uri}?{urlencode(params)}"
        else:
            url = f"{self._host}{uri}"
        return await self.request("GET", url, headers=headers or self.headers)

    async def _base_post(self, uri: str, data: dict, headers: Optional[Dict] = None) -> Any:
        """
        无签名的通用 POST 请求。

        子类如需签名（如 XHS、Bilibili、Zhihu），应覆盖 post() 方法，
        但在不需要签名时可直接调用此方法。
        """
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request("POST", f"{self._host}{uri}", data=json_str, headers=headers or self.headers)

    # ==================== 媒体下载 ====================

    async def download_media(
        self,
        url: str,
        follow_redirects: bool = True,
        extra_headers: Optional[Dict] = None,
    ) -> Optional[bytes]:
        """
        统一媒体文件下载，替代各平台各自的 get_*_media() 方法。

        Args:
            url: 媒体文件 URL
            follow_redirects: 是否跟随 302 重定向（默认 True）
            extra_headers: 额外请求头（如 Bilibili 需要 Referer）

        Returns:
            文件内容的 bytes，失败返回 None
        """
        await self._refresh_proxy_if_expired()

        async with make_async_client(proxy=self.proxy, follow_redirects=follow_redirects) as client:
            try:
                response = await client.request(
                    "GET", url, timeout=self.timeout, headers=extra_headers
                )
                response.raise_for_status()
                if not response.reason_phrase == "OK" and response.status_code not in (200, 206):
                    utils.logger.error(
                        f"[{self.__class__.__name__}.download_media] request {url} err, "
                        f"status: {response.status_code}, res: {response.text}"
                    )
                    return None
                return response.content
            except httpx.HTTPError as exc:
                utils.logger.error(
                    f"[{self.__class__.__name__}.download_media] "
                    f"{exc.__class__.__name__} for {exc.request.url} - {exc}"
                )
                return None

    # ==================== 通用分页循环 ====================

    async def _paginate_comments(
        self,
        fetch_fn: Callable,
        has_more_fn: Callable,
        extract_fn: Callable,
        note_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 10,
        sub_comment_fetcher: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        通用评论分页循环，消除各平台评论遍历的重复代码。

        Args:
            fetch_fn: async (note_id, cursor) -> response_dict，获取一页评论
            has_more_fn: (response_dict) -> (has_more: bool, next_cursor)，判断是否有更多
            extract_fn: (response_dict) -> List[Dict]，从响应中提取评论列表
            note_id: 帖子/视频 ID
            crawl_interval: 每次请求间隔（秒）
            callback: 可选回调 async (note_id, comments) -> None
            max_count: 最大获取评论数
            sub_comment_fetcher: 可选的子评论获取函数
                async (comments, crawl_interval, callback) -> List[Dict]

        Returns:
            所有评论的列表
        """
        result: List[Dict] = []
        has_more = True
        cursor = None

        while has_more and len(result) < max_count:
            res = await fetch_fn(note_id, cursor)
            has_more, cursor = has_more_fn(res)
            comments = extract_fn(res)

            if not comments:
                break

            if len(result) + len(comments) > max_count:
                comments = comments[:max_count - len(result)]

            if callback:
                await callback(note_id, comments)

            await asyncio.sleep(crawl_interval)
            result.extend(comments)

            if sub_comment_fetcher:
                sub_comments = await sub_comment_fetcher(comments, crawl_interval, callback)
                result.extend(sub_comments)

        return result

    async def _paginate_creator_posts(
        self,
        fetch_fn: Callable,
        has_more_fn: Callable,
        extract_fn: Callable,
        creator_id: str,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: Optional[int] = None,
    ) -> List[Dict]:
        """
        通用创作者帖子分页循环，消除各平台创作者帖子遍历的重复代码。

        Args:
            fetch_fn: async (creator_id, cursor) -> response_dict，获取一页帖子
            has_more_fn: (response_dict) -> (has_more: bool, next_cursor)，判断是否有更多
            extract_fn: (response_dict) -> List[Dict]，从响应中提取帖子列表
            creator_id: 创作者 ID
            crawl_interval: 每次请求间隔（秒）
            callback: 可选回调 async (posts) -> None
            max_count: 最大获取帖子数，默认使用 config.CRAWLER_MAX_NOTES_COUNT

        Returns:
            所有帖子的列表
        """
        import config
        if max_count is None:
            max_count = getattr(config, "CRAWLER_MAX_NOTES_COUNT", 999999)

        result: List[Dict] = []
        has_more = True
        cursor = None

        while has_more and len(result) < max_count:
            res = await fetch_fn(creator_id, cursor)
            if not res:
                utils.logger.error(
                    f"[{self.__class__.__name__}._paginate_creator_posts] "
                    f"Empty response for creator {creator_id}, stopping."
                )
                break

            has_more, cursor = has_more_fn(res)
            items = extract_fn(res)

            if not items:
                break

            remaining = max_count - len(result)
            if remaining <= 0:
                break
            items = items[:remaining]

            if callback:
                await callback(items)

            result.extend(items)
            await asyncio.sleep(crawl_interval)

        return result
