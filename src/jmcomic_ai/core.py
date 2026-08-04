import asyncio
import functools
import json
import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from mcp.server.fastmcp import Context
except ImportError:
    Context = Any  # type: ignore

from jmcomic import (
    JmAlbumComment,
    JmAlbumCommentPage,
    JmAlbumDetail,
    JmCategoryPage,
    JmcomicClient,
    JmcomicText,
    JmDownloader,
    JmMagicConstants,
    JmModuleConfig,
    JmOption,
    JmPageContent,
    JmSearchPage,
    create_option_by_file,
    get_jm_task_context,
    jm_logger,
    jm_task_context,
)

ENV_OPTION_PATH = "JM_OPTION_PATH"
ENV_LOG_PATH = "JM_LOG_PATH"
ENV_TASK_LOG_DIR = "JM_TASK_LOG_DIR"
DEFAULT_OPTION_PATH = Path.home() / ".jmcomic" / "option.yml"
DEFAULT_LOG_PATH = Path.home() / ".jmcomic-ai" / "jmcomic_ai.log"
DEFAULT_TASK_LOG_DIR = Path.home() / ".jmcomic-ai" / "logs"
GLOBAL_LOG_HANDLER_NAME = "jmcomic-ai-global-file"

# Shared friendly-vocabulary -> JmMagicConstants mappings.
# Used by both search_album and browse_albums so the order_by / time_range
# vocabulary stays identical across the two tools (DRY).
ORDER_BY_MAP: dict[str, str] = {
    "latest": JmMagicConstants.ORDER_BY_LATEST,  # mr
    "likes": JmMagicConstants.ORDER_BY_LIKE,  # tf
    "views": JmMagicConstants.ORDER_BY_VIEW,  # mv
    "pictures": JmMagicConstants.ORDER_BY_PICTURE,  # mp
    "score": JmMagicConstants.ORDER_BY_SCORE,  # tr
    "comments": JmMagicConstants.ORDER_BY_COMMENT,  # md
}

TIME_RANGE_MAP: dict[str, str] = {
    "all": JmMagicConstants.TIME_ALL,
    "day": JmMagicConstants.TIME_TODAY,
    "today": JmMagicConstants.TIME_TODAY,
    "week": JmMagicConstants.TIME_WEEK,
    "month": JmMagicConstants.TIME_MONTH,
}


def _get_record_task_context(record: logging.LogRecord) -> Mapping[str, Any]:
    """Read JM task context from a record, falling back to the current context."""
    context = getattr(record, "jm_task_context", None)
    if isinstance(context, Mapping):
        return context
    return dict(get_jm_task_context())


def _configure_logger_file_only(
    logger: logging.Logger,
    global_handler: logging.FileHandler,
) -> None:
    """Route a logger to files only while preserving per-task file handlers."""
    for handler in list(logger.handlers):
        if handler is global_handler:
            continue
        if not isinstance(handler, logging.FileHandler) or handler.get_name() == GLOBAL_LOG_HANDLER_NAME:
            logger.removeHandler(handler)
            if handler.get_name() == GLOBAL_LOG_HANDLER_NAME:
                handler.close()

    if global_handler not in logger.handlers:
        logger.addHandler(global_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _get_global_file_handler(log_path: Path) -> logging.FileHandler:
    """Reuse one process-wide file handler for both JMComic logger namespaces."""
    for logger in (logging.getLogger("jmcomic_ai"), jm_logger):
        for handler in logger.handlers:
            if (
                isinstance(handler, logging.FileHandler)
                and handler.get_name() == GLOBAL_LOG_HANDLER_NAME
                and Path(handler.baseFilename).resolve() == log_path
            ):
                return handler

    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.set_name(GLOBAL_LOG_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    return handler


class _TaskLogFilter(logging.Filter):
    """Keep only records emitted by one MCP download task."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id

    def filter(self, record: logging.LogRecord) -> bool:
        context = _get_record_task_context(record)
        if context.get("task_id") != self.task_id:
            return False

        fields = [f"task_id={self.task_id}"]
        mcp_tool = context.get("mcp_tool")
        download_type = context.get("download_type")
        jm_id = context.get("jm_id")
        if mcp_tool is not None:
            fields.append(f"mcp_tool={mcp_tool}")
        if download_type is not None and jm_id is not None:
            fields.append(f"{download_type}={jm_id}")
        elif download_type is not None:
            fields.append(f"download_type={download_type}")
        elif jm_id is not None:
            fields.append(f"jm_id={jm_id}")
        record.jm_task_context_text = "; ".join(fields)
        return True


class _McpDownloaderBase(JmDownloader):  # type: ignore[misc, valid-type]
    """共享 ctx/logger/safe_ctx_call 接线的基类。"""

    def __init__(self, option: Any, ctx: Any, loop: Any, service_logger: logging.Logger, threading_mod: Any) -> None:
        super().__init__(option)
        self.ctx = ctx
        self.loop = loop
        self.service_logger = service_logger
        self.threading_mod = threading_mod

    def _safe_ctx_call(self, coro_func: Any, error_msg_prefix: str) -> None:
        """安全地调用 MCP Context 异步方法，防止进度报告失败中止下载"""
        if self.ctx:
            try:
                future = asyncio.run_coroutine_threadsafe(coro_func(), self.loop)
                def _on_done(f: Any) -> None:
                    try:
                        f.result()
                    except Exception as e:
                        self.service_logger.warning(f"{error_msg_prefix}: {e}")
                future.add_done_callback(_on_done)
            except Exception as e:
                self.service_logger.warning(f"{error_msg_prefix}: {e}")


class McpProgressDownloader(_McpDownloaderBase):
    def __init__(self, option: Any, ctx: Any, loop: Any, service_logger: logging.Logger, threading_mod: Any) -> None:
        super().__init__(option, ctx, loop, service_logger, threading_mod)
        self.photo_progress: dict[Any, dict[str, int]] = {}  # {photo_id: {"current": 0, "total": 0}}
        self.lock = self.threading_mod.Lock()

    def before_album(self, album: Any) -> None:
        super().before_album(album)
        # Send detailed album info
        album_dict = {
            "id": str(album.album_id),
            "title": str(album.name),
            "author": str(album.author),
            "chapter_count": len(album),
            "tags": album.tags,
        }
        msg = f"📚 Album Info: {json.dumps(album_dict, ensure_ascii=False)}"
        self.service_logger.info(msg)
        self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send album info to ctx")

    def after_album(self, album: Any) -> None:
        super().after_album(album)
        msg = f"✅ Album download completed: {album.name}"
        self.service_logger.info(msg)
        self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send album completion to ctx")

    def before_photo(self, photo: Any) -> None:
        super().before_photo(photo)
        with self.lock:
            self.photo_progress[photo.photo_id] = {
                "current": 0,
                "total": len(photo)
            }
        msg = f"📖 Starting chapter: {photo.photo_id} - {photo.name} ({len(photo)} pages)"
        self.service_logger.info(msg)
        self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send chapter start to ctx")

    def after_image(self, image: Any, img_save_path: str) -> None:
        super().after_image(image, img_save_path)
        photo_id = image.from_photo.photo_id
        current = 0
        total = 0

        with self.lock:
            if photo_id in self.photo_progress:
                self.photo_progress[photo_id]["current"] += 1
                current = self.photo_progress[photo_id]["current"]
                total = self.photo_progress[photo_id]["total"]

        if total > 0:
            msg = f"Chapter {photo_id}: {current}/{total}"
            self.service_logger.info(msg)
            self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send image progress to ctx")


class McpPhotoProgressDownloader(_McpDownloaderBase):
    def __init__(self, option: Any, ctx: Any, loop: Any, service_logger: logging.Logger, threading_mod: Any) -> None:
        super().__init__(option, ctx, loop, service_logger, threading_mod)
        self.current = 0
        self.total = 0
        self.lock = self.threading_mod.Lock()

    def before_photo(self, photo: Any) -> None:
        super().before_photo(photo)
        self.total = len(photo)

        photo_dict = {
            "id": str(photo.photo_id),
            "name": str(photo.name),
            "total_pages": self.total,
        }
        msg = f"📖 Photo Info: {json.dumps(photo_dict, ensure_ascii=False)}"
        self.service_logger.info(msg)
        self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send photo info to ctx")

    def after_photo(self, photo: Any) -> None:
        super().after_photo(photo)
        msg = f"✅ Photo download completed: {photo.name} ({self.current} images)"
        self.service_logger.info(msg)
        self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send photo completion to ctx")

    def after_image(self, image: Any, img_save_path: str) -> None:
        super().after_image(image, img_save_path)
        with self.lock:
            self.current += 1
            current = self.current
            total = self.total

        if total > 0:
            percentage = int((current / total) * 100)
            msg = f"Downloading: {percentage}% ({current}/{total})"
        else:
            msg = f"Downloading: {current} images downloaded"

        self.service_logger.info(msg)
        if self.ctx:
            self._safe_ctx_call(lambda: self.ctx.info(msg), "Failed to send download progress to ctx")
            if hasattr(self.ctx, 'report_progress') and self.total > 0:
                self._safe_ctx_call(
                    lambda: self.ctx.report_progress(self.current, self.total),
                    "Failed to report progress to ctx"
                )


def _build_progress_downloaders(
    ctx: Any,
    loop: Any,
    service_logger: logging.Logger,
    threading_mod: Any,
) -> tuple[Any, Any]:
    """
    构建 album 级与 photo 级两个带进度上报的 JmDownloader 工厂（通过 functools.partial 预绑定参数）。

    [not a tool]

    Args:
        ctx: MCP Context，可能为 None。
        loop: 调用方所在的事件循环（用于 run_coroutine_threadsafe）。
        service_logger: 日志器。
        threading_mod: ``threading`` 模块（album 级进度需要 Lock）。

    Returns:
        (album_downloader_partial, photo_downloader_partial)
    """
    return (
        functools.partial(
            McpProgressDownloader,
            ctx=ctx,
            loop=loop,
            service_logger=service_logger,
            threading_mod=threading_mod
        ),
        functools.partial(
            McpPhotoProgressDownloader,
            ctx=ctx,
            loop=loop,
            service_logger=service_logger,
            threading_mod=threading_mod
        )
    )


def resolve_option_path(cli_path: str | None = None, logger: logging.Logger | None = None) -> Path:
    """
    Resolve jmcomic option path with priority: CLI > Environment Variable > Default.

    This function determines the configuration file path using a three-tier resolution strategy:
    1. CLI argument (highest priority)
    2. Environment variable (JM_OPTION_PATH)
    3. Default path (~/.jmcomic/option.yml)

    Args:
        cli_path: Optional path provided via CLI argument. If specified, this takes highest priority.
        logger: Optional logger instance for logging resolution steps. If None, uses default logger.

    Returns:
        Resolved absolute Path to the option file.

    Examples:
        >>> # Use default path
        >>> path = resolve_option_path()
        >>> # Use CLI-provided path
        >>> path = resolve_option_path("/custom/path/option.yml")
        >>> # Use with custom logger
        >>> path = resolve_option_path(logger=my_logger)
    """
    if logger is None:
        logger = logging.getLogger("jmcomic_ai")

    # 1. CLI Argument
    if cli_path:
        path = Path(cli_path).resolve()
        logger.info(f"Found via [CLI argument] -> {path}")
        return path

    # 2. Environment Variable
    env_path = os.getenv(ENV_OPTION_PATH)
    if env_path:
        path = Path(env_path).resolve()
        logger.info(f"Found via [Environment variable: {ENV_OPTION_PATH}] -> {path}")
        return path

    # 3. Default Path
    logger.info(f"Using [Default path] -> {DEFAULT_OPTION_PATH}")
    return DEFAULT_OPTION_PATH


class JmcomicService:
    def __init__(
        self,
        option_path: str | None = None,
        task_log_dir: str | None = None,
        log_path: str | None = None,
    ):
        self._setup_logging(log_path)
        self.option_path = resolve_option_path(option_path, self.logger)
        self.task_log_dir = (
            Path(task_log_dir or os.getenv(ENV_TASK_LOG_DIR) or DEFAULT_TASK_LOG_DIR).expanduser().resolve()
        )
        self.option = self._load_option()
        self.client = self.option.build_jm_client()
        self._ensure_init()

    def _load_option(self) -> JmOption:
        self.logger.info(f"Loading jmcomic option from: {self.option_path}")
        if not self.option_path.exists():
            self.logger.warning(f"Option file NOT found. Generating default at: {self.option_path}")
            # Generate default if not exists
            self.option_path.parent.mkdir(parents=True, exist_ok=True)
            default_option = JmModuleConfig.option_class().default()
            default_option.to_file(str(self.option_path))
            self.logger.info("Default option generated and loaded.")
            return default_option

        option = create_option_by_file(str(self.option_path))
        self.logger.info("Option loaded successfully.")
        return option

    def _ensure_init(self):
        """Ensure necessary initialization"""
        pass

    def _setup_logging(self, log_path: str | None = None):
        """Route jmcomic and jmcomic_ai logs to one global file only."""
        self.log_path = Path(
            log_path or os.getenv(ENV_LOG_PATH) or DEFAULT_LOG_PATH
        ).expanduser().resolve()
        self.logger = logging.getLogger("jmcomic_ai")
        global_handler = _get_global_file_handler(self.log_path)
        _configure_logger_file_only(logging.getLogger(), global_handler)
        _configure_logger_file_only(self.logger, global_handler)
        _configure_logger_file_only(jm_logger, global_handler)
        self.logger.info(f"Logging initialized: path={self.log_path}")

    @contextmanager
    def _download_task_log(self, tool_name: str, jm_id: str) -> Iterator[tuple[str, Path]]:
        """Create and route logs for one MCP download tool invocation."""
        safe_jm_id = "".join(char for char in str(jm_id) if char.isalnum() or char in "-_")[:48] or "unknown"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        task_id = f"{tool_name}-{safe_jm_id}-{uuid4().hex[:8]}"

        self.task_log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.task_log_dir / f"{timestamp}-{task_id}.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.addFilter(_TaskLogFilter(task_id))
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(threadName)s] [%(levelname)s] [%(jm_task_context_text)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        self.logger.addHandler(handler)
        jm_logger.addHandler(handler)
        try:
            with jm_task_context(task_id=task_id, mcp_tool=tool_name):
                self.logger.info(f"Task started: tool={tool_name}, jm_id={jm_id}")
                try:
                    yield task_id, log_path
                finally:
                    self.logger.info(f"Task finished: tool={tool_name}, jm_id={jm_id}")
        finally:
            self.logger.removeHandler(handler)
            jm_logger.removeHandler(handler)
            handler.close()

    def reload_option(self):
        """
        [not a tool]
        """
        self.option = self._load_option()
        self.client = self.option.build_jm_client()

    def update_option(self, option_updates: dict[str, Any]) -> str:
        """
        更新 JMComic 配置并保存到文件。

        重要提示：此工具仅执行有限的验证。
        在调用此工具之前，建议先查看以下资源了解 JmOption 语法：
        - `jmcomic://option/schema`: 参数类型和结构约束。
        - `jmcomic://option/reference`: 字段详细说明和示例。

        参数:
            option_updates: 要合并的配置更新字典。
                           支持对 client、download、dir_rule 等进行嵌套更新。

        返回:
            包含文件路径的成功消息，或错误消息。

        示例:
            option_updates = {
                "client": {"impl": "api"},
                "download": {"threading": {"image": 50}}
            }
        """
        try:
            # 1. 获取当前配置
            current_option = self.option.deconstruct()

            # 2. 合并配置
            merged_option = JmOption.merge_default_dict(option_updates, current_option)

            # 3. 验证配置（construct 会校验）
            new_option = JmOption.construct(merged_option)

            # 4. 保存到文件
            new_option.to_file(str(self.option_path))

            # 5. 更新内存中的 option
            self.reload_option()

            self.logger.info("option updated successfully")
            return f"option updated and saved to {self.option_path}"

        except Exception as e:
            self.logger.error(f"option update failed: {str(e)}")
            return f"option update failed: {str(e)}"

    def get_client(self) -> JmcomicClient:
        """
        [not a tool]
        """
        return self.client

    # --- Data Conversion Helper Methods ---

    def _parse_search_page(self, page: JmPageContent) -> dict[str, Any]:
        """Parse JmSearchPage/JmCategoryPage content to dictionary"""
        albums = []

        # 使用 jmcomic 提供的原始 content 获取完整信息
        for album_id, ainfo in page.content:
            album_id = str(album_id)
            album_dict = {
                "id": album_id,
                "title": str(ainfo.get("name", "")),
                "tags": ainfo.get("tags", []),
                "cover_url": JmcomicText.get_album_cover_url(album_id),
            }
            # 如果有 likes 信息,也添加进去
            if "likes" in ainfo:
                album_dict["likes"] = ainfo["likes"]

            albums.append(album_dict)

        return {
            "albums": albums,
            "total_count": int(page.total) if hasattr(page, "total") else len(albums),
        }

    def _parse_album_detail(self, album: JmAlbumDetail) -> dict[str, Any]:
        """Convert JmAlbumDetail object to dictionary"""
        # Strictly use object attributes as defined in JmAlbumDetail source
        return {
            "id": str(album.album_id),
            "title": str(album.name),
            "author": str(album.author),
            "likes": album.likes,
            "views": album.views,
            "tags": album.tags,
            "actors": album.actors,
            "description": str(album.description),
            "chapter_count": len(album),
            "update_time": str(album.update_date),
            "cover_url": JmcomicText.get_album_cover_url(album.album_id),
        }

    def _parse_album_comment(self, comment: JmAlbumComment) -> dict[str, Any]:
        """Convert one album comment and its nested replies to a dictionary."""
        return {
            "comment_id": str(comment.comment_id) if comment.comment_id is not None else None,
            "album_id": str(comment.album_id) if comment.album_id is not None else None,
            "user_id": str(comment.user_id) if comment.user_id is not None else None,
            "parent_comment_id": (str(comment.parent_comment_id) if comment.parent_comment_id is not None else None),
            "content": str(comment.content or ""),
            "username": str(comment.username or ""),
            "nickname": str(comment.nickname or ""),
            "is_spoiler": bool(comment.is_spoiler),
            "created_at": comment.created_at,
            "likes": comment.likes,
            "replies": [self._parse_album_comment(reply) for reply in comment.replies],
        }

    def _parse_album_comment_page(
        self,
        album_id: str,
        page_number: int,
        comment_page: JmAlbumCommentPage,
    ) -> dict[str, Any]:
        """Convert an album comment page to the stable MCP response shape."""
        return {
            "album_id": str(album_id),
            "page": page_number,
            "page_size": comment_page.page_size,
            "total": comment_page.total,
            "page_count": comment_page.page_count,
            "comment_count": comment_page.comment_count,
            "comments": [self._parse_album_comment(comment) for comment in comment_page],
        }

    # --- Business Methods ---

    def search_album(
        self,
        keyword: str,
        page: int = 1,
        main_tag: int = 0,
        order_by: str = "latest",
        time_range: str = "all",
        category: str = "all",
    ) -> dict[str, Any]:
        """
        搜索本子，支持高级过滤选项。

        参数:
            keyword: 搜索关键词（支持本子ID、标题、作者、标签等）。
            page: 页码，从1开始（默认值：1）。
            main_tag: 搜索范围 - 0 (站内), 1 (作品), 2 (作者), 3 (标签), 4 (角色)（默认值：0）。
            order_by: 排序方式，与 browse_albums 词汇一致。可选值：
                - "latest": 最新更新
                - "likes": 最多点赞
                - "views": 最多观看
                - "pictures": 最多图片
                - "score": 评分最高
                - "comments": 评论最多
                （默认值："latest"）。
            time_range: 时间过滤，与 browse_albums 词汇一致。可选值：
                - "all": 全部时间
                - "day" 或 "today": 今天
                - "week": 本周
                - "month": 本月
                （默认值："all"）。
            category: 分类过滤 - "all" 或具体的 CID（默认值："all"）。

        返回:
            包含以下内容的字典：
                - albums: 本子信息列表。
                - total_count: 结果总数。
                - error: 如果 order_by / time_range 参数无效，则包含错误信息（可选）。
        """
        client = self.get_client()

        # Map friendly order_by / time_range vocabulary to JmMagicConstants
        # (shared with browse_albums for a consistent tool surface).
        order_value = ORDER_BY_MAP.get(order_by.lower())
        time_value = TIME_RANGE_MAP.get(time_range.lower())

        if order_value is None:
            valid_orders = ", ".join(ORDER_BY_MAP.keys())
            error_msg = f"Invalid order_by: {order_by}. Valid options: {valid_orders}"
            self.logger.error(error_msg)
            return {"albums": [], "total_count": 0, "error": error_msg}

        if time_value is None:
            valid_times = ", ".join(TIME_RANGE_MAP.keys())
            error_msg = f"Invalid time_range: {time_range}. Valid options: {valid_times}"
            self.logger.error(error_msg)
            return {"albums": [], "total_count": 0, "error": error_msg}

        # Call core search method
        search_page: JmSearchPage = client.search(
            keyword,
            page=page,
            main_tag=main_tag,
            order_by=order_value,
            time=time_value,
            category=category,
            sub_category=None,
        )

        self.logger.info(f"Search finished: keyword={keyword}, results={len(search_page)}")
        return self._parse_search_page(search_page)

    def browse_albums(
        self,
        category: str = "all",
        time_range: str = "all",
        order_by: str = "latest",
        page: int = 1
    ) -> dict[str, Any]:
        """
        浏览、过滤、排行本子，支持灵活的分类、时间范围和排序选项。

        该工具结合了分类浏览和排行榜功能，支持：
        - 浏览特定分类（同人、韩漫等）。
        - 按时间范围过滤（今天、本周、本月、全部）。
        - 按不同标准排序（点赞、观看、最新、图片数、评分、评论数）。

        参数:
            category: 分类过滤器。可选值：
                - "all" 或 "0": 全部分类
                - "doujin": 同人
                - "single": 单本
                - "short": 短篇
                - "hanman": 韩漫
                - "meiman": 美漫
                - "doujin_cosplay": Cosplay
                - "3D": 3D
                - "another": 其他
                - "english_site": 英文站
                (默认值: "all")

            time_range: 时间范围过滤器。可选值：
                - "all": 全部时间
                - "day" 或 "today": 今天
                - "week": 本周
                - "month": 本月
                (默认值: "all")

            order_by: 排序方式。可选值：
                - "latest": 最新更新
                - "likes": 最多点赞
                - "views": 最多观看
                - "pictures": 最多图片
                - "score": 评分最高
                - "comments": 评论最多
                (默认值: "latest")

            page: 页码，从1开始（默认值: 1）

        返回:
            包含以下内容的字典：
                - albums: 本子简要信息列表 (id, title, tags, cover_url)
                - total_count: 结果总数
                - error: 如果参数无效，则包含错误信息（可选）

            注意：该 API 不包含详细统计数据（点赞/观看/作者）。
                  请使用 get_album_detail() 获取特定本子的完整信息。

        示例:
            # 1. 获取本月点赞排行 (月榜)
            browse_albums(time_range="month", order_by="likes")

            # 2. 浏览同人志分类 (最新)
            browse_albums(category="doujin", order_by="latest")

            # 3. 浏览本周热门韩漫 (特定分类排行榜)
            browse_albums(category="hanman", time_range="week", order_by="views")
        """
        client = self.get_client()

        # Category mapping
        category_map = {
            "all": JmMagicConstants.CATEGORY_ALL,
            "0": JmMagicConstants.CATEGORY_ALL,
            "doujin": JmMagicConstants.CATEGORY_DOUJIN,
            "single": JmMagicConstants.CATEGORY_SINGLE,
            "short": JmMagicConstants.CATEGORY_SHORT,
            "hanman": JmMagicConstants.CATEGORY_HANMAN,
            "meiman": JmMagicConstants.CATEGORY_MEIMAN,
            "doujin_cosplay": JmMagicConstants.CATEGORY_DOUJIN_COSPLAY,
            "3d": JmMagicConstants.CATEGORY_3D,
            "another": JmMagicConstants.CATEGORY_ANOTHER,
            "english_site": JmMagicConstants.CATEGORY_ENGLISH_SITE,
        }

        # Validate and map parameters (time_range / order_by use shared maps)
        category_value = category_map.get(category.lower())
        time_value = TIME_RANGE_MAP.get(time_range.lower())
        order_value = ORDER_BY_MAP.get(order_by.lower())

        if category_value is None:
            valid_categories = ", ".join(category_map.keys())
            error_msg = f"Invalid category: {category}. Valid options: {valid_categories}"
            self.logger.error(error_msg)
            return {"albums": [], "total_count": 0, "error": error_msg}

        if time_value is None:
            valid_times = ", ".join(TIME_RANGE_MAP.keys())
            error_msg = f"Invalid time_range: {time_range}. Valid options: {valid_times}"
            self.logger.error(error_msg)
            return {"albums": [], "total_count": 0, "error": error_msg}

        if order_value is None:
            valid_orders = ", ".join(ORDER_BY_MAP.keys())
            error_msg = f"Invalid order_by: {order_by}. Valid options: {valid_orders}"
            self.logger.error(error_msg)
            return {"albums": [], "total_count": 0, "error": error_msg}

        # Call unified categories_filter API
        search_page: JmCategoryPage = client.categories_filter(
            page=page,
            time=time_value,
            category=category_value,
            order_by=order_value,
            sub_category=None,
        )

        self.logger.info(
            f"Browse albums: category={category}, time_range={time_range}, "
            f"order_by={order_by}, page={page}, results={len(search_page)}"
        )

        return self._parse_search_page(search_page)

    async def download_album(self, album_id: str, ctx: Context | None = None) -> dict[str, Any]:
        """
        在后台下载整个本子。

        这是一个阻塞操作，会等待下载完成后返回。
        下载进度会通过日志和 MCP Context（如果可用）实时报告。

        参数:
            album_id: 要下载的本子 ID (例如 "123456")
            ctx: MCP Context，用于实时报告进度和日志（由 FastMCP 自动注入）

        返回:
            包含以下内容的字典：
                - status: "success" 或 "failed"
                - album_id: 本子 ID
                - title: 本子标题
                - download_path: 下载目录的绝对路径
                - task_id: 本次 MCP 下载调用的任务 ID
                - log_path: 本次调用专属日志文件的绝对路径
                - error: 如果失败则包含错误信息
        """
        import threading

        with self._download_task_log("download-album", album_id) as (task_id, log_path):
            album = None
            target_path: Path | str = ""
            try:
                album = self.get_client().get_album_detail(album_id)
                target_path = self.option.dir_rule.decide_album_root_dir(album)

                loop = asyncio.get_running_loop()
                McpProgressDownloader, _ = _build_progress_downloaders(ctx, loop, self.logger, threading)

                def _blocking_download():
                    self.logger.info(f"Starting blocking download for album {album_id}")
                    self.option.download_album(album_id, downloader=McpProgressDownloader)
                    self.logger.info(f"Download completed for album {album_id}")
                    return "success"

                status = await asyncio.to_thread(_blocking_download)
                error_msg = None
            except Exception as e:
                status = "failed"
                error_msg = str(e)
                self.logger.exception(f"Download failed for album {album_id}")

            return {
                "status": status,
                "album_id": album_id,
                "title": str(album.name) if album is not None else "",
                "download_path": str(target_path),
                "task_id": task_id,
                "log_path": str(log_path),
                "error": error_msg,
            }

    async def download_photo(self, photo_id: str, ctx: Context | None = None) -> dict[str, Any]:
        """
        下载本子中的特定章节。

        参数:
            photo_id: 要下载的章节 ID (例如 "123456")
            ctx: MCP Context，用于实时报告进度和日志（由 FastMCP 自动注入）

        返回:
            包含以下内容的字典：
                - status: "success" 或 "failed"
                - photo_id: 章节 ID
                - image_count: 下载的图片数量
                - download_path: 下载目录的绝对路径
                - task_id: 本次 MCP 下载调用的任务 ID
                - log_path: 本次调用专属日志文件的绝对路径
                - error: 如果失败则包含错误信息
        """
        import threading

        with self._download_task_log("download-photo", photo_id) as (task_id, log_path):
            download_path: Path | str = ""
            image_count = 0
            try:
                loop = asyncio.get_running_loop()
                _, McpPhotoProgressDownloader = _build_progress_downloaders(ctx, loop, self.logger, threading)

                def _blocking_download():
                    self.logger.info(f"Starting download for photo {photo_id}")
                    result = self.option.download_photo(photo_id, downloader=McpPhotoProgressDownloader)
                    self.logger.info(f"Download completed for photo {photo_id}")
                    return result.detail

                photo = await asyncio.to_thread(_blocking_download)
                status = "success"
                download_path = self.option.decide_image_save_dir(photo)
                image_count = len(photo)
                error_msg = None
            except Exception as e:
                status = "failed"
                error_msg = str(e)
                self.logger.exception(f"Download failed for photo {photo_id}")

            return {
                "status": status,
                "photo_id": photo_id,
                "image_count": image_count,
                "download_path": str(download_path),
                "task_id": task_id,
                "log_path": str(log_path),
                "error": error_msg,
            }

    def login(self, username: str, password: str) -> str:
        """
        登录 JMComic 账户以访问更多功能（如收藏夹、高级内容等）。
        登录后的会话 Cookie 会自动保存，供后续请求使用。

        参数:
            username: 用户名
            password: 密码

        返回:
            登录成功或失败的消息。
        """
        client = self.get_client()
        try:
            client.login(username, password)
            self.logger.info(f"Successfully logged in as {username}")
            return f"Successfully logged in as {username}"
        except Exception as e:
            self.logger.error(f"Login failed for {username}: {str(e)}")
            return f"Login failed: {str(e)}"

    def get_album_detail(self, album_id: str) -> dict[str, Any]:
        """
        获取特定本子的详细信息。

        参数:
            album_id: 本子 ID (例如 "123456")

        返回:
            包含详细信息的字典：id, title, author, likes, views,
            tags, actors, description, chapter_count, update_time, cover_url。
        """
        client = self.get_client()
        album = client.get_album_detail(album_id)
        return self._parse_album_detail(album)

    def get_album_comments(self, album_id: str, page: int = 1) -> dict[str, Any]:
        """
        获取本子的一页评论，包括递归回评和剧透标识。

        参数:
            album_id: 本子 ID (例如 "302820")。
            page: 评论页码，从 1 开始（默认值：1）。

        返回:
            包含以下内容的字典：
                - album_id: 本子 ID
                - page: 当前页码
                - page_size: 每页主评论数量
                - total: 全部分页的主评论总数；不可用时为 null
                - page_count: 总页数；不可用时为 null
                - comment_count: 当前页主评论与所有层级回评总数
                - comments: 评论列表，每条评论包含 replies 和 is_spoiler
        """
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")

        self.logger.info(f"Fetching album comments: album_id={album_id}, page={page}")
        comment_page = self.get_client().album_pagination(album_id, page=page)
        result = self._parse_album_comment_page(album_id, page, comment_page)
        self.logger.info(
            f"Album comments fetched: album_id={album_id}, page={page}, comments={result['comment_count']}"
        )
        return result

    def download_cover(self, album_id: str) -> str:
        """
        下载特定本子的封面图片。
        封面将保存到默认下载目录下的 'covers' 子目录中。

        参数:
            album_id: 本子 ID (例如 "123456")

        返回:
            包含保存路径的成功消息。
        """
        client = self.get_client()
        # Verify album exists
        client.get_album_detail(album_id)

        # 使用 .base_dir 属性而非 .get() 方法
        cover_dir = Path(self.option.dir_rule.base_dir) / "covers"
        cover_dir.mkdir(parents=True, exist_ok=True)
        cover_path = cover_dir / f"{album_id}.jpg"

        # 确保路径是字符串类型传递给 download_album_cover
        client.download_album_cover(album_id, str(cover_path))

        self.logger.info(f"Cover downloaded for album {album_id} to {cover_path}")
        return f"Cover downloaded to {cover_path}"

    def post_process(self, album_id: str, process_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        对已下载的本子进行后处理（生成 Zip、PDF 或长图）。

        参数:
            album_id: 要处理的本子 ID。
            process_type: 后处理类型，可选值为 "zip", "img2pdf", "long_img"。
            params: 后处理参数字典。支持：
                - `dir_rule`: 输出路径规则。格式: `{"rule": "Bd/{Atitle}.zip", "base_dir": "D:/Comics"}`。
                - `delete_original_file`: 布尔值，处理完成后是否删除原始文件。

        返回:
            包含以下内容的字典：
                - status: "success" 或 "error"
                - process_type: 后处理类型
                - album_id: 本子 ID
                - output_path: 输出文件/目录的绝对路径
                - is_directory: 输出是否为目录
                - message: 成功或错误消息
        """
        from jmcomic import JmAlbumDetail, JmModuleConfig

        self.logger.info(f"Starting post-process '{process_type}' for album {album_id}")

        try:
            # 1. Get album metadata
            album: JmAlbumDetail = self.get_client().get_album_detail(album_id)

            # 2. Build mock downloader for plugin state
            class MockDownloader:
                def __init__(self):
                    self.download_success_dict = {}

            mock_downloader = MockDownloader()
            photo_dict = {}
            total_images = 0

            for photo in album:
                photo_dir = Path(self.option.decide_image_save_dir(photo))
                if not photo_dir.exists():
                    continue

                images = []
                for file in sorted(photo_dir.iterdir()):
                    if (
                        file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif')
                        and not file.name.startswith('.')
                    ):
                        images.append((str(file), None))

                if images:
                    photo_dict[photo] = images
                    total_images += len(images)

            if not photo_dict:
                expected_path = self.option.dir_rule.decide_album_root_dir(album)
                self.logger.error(f"No downloaded images found. Expected path: {expected_path}")
                return {
                    "status": "error",
                    "album_id": album_id,
                    "process_type": process_type,
                    "output_path": "",
                    "is_directory": False,
                    "message": f"Error: No downloaded images found for album {album_id}."
                }

            mock_downloader.download_success_dict[album] = photo_dict
            self.logger.info(f"Found {len(photo_dict)} chapters and {total_images} images.")

            # 3. Setup Plugin and Parameters
            pclass = JmModuleConfig.REGISTRY_PLUGIN.get(process_type)
            if pclass is None:
                return {
                    "status": "error",
                    "album_id": album_id,
                    "process_type": process_type,
                    "output_path": "",
                    "is_directory": False,
                    "message": f"Plugin '{process_type}' not found."
                }

            actual_params = params.copy() if params else {}

            if 'filename_rule' not in actual_params:
                actual_params['filename_rule'] = 'Aid' if process_type != 'zip' else 'Ptitle'

            actual_params.update({'album': album, 'downloader': mock_downloader})

            # Instantiate and invoke
            plugin = pclass.build(self.option)
            plugin.invoke(**actual_params)

            # 4. Predict Output Path
            suffix_map = {'zip': actual_params.get('suffix', 'zip'), 'img2pdf': 'pdf', 'long_img': 'png'}
            suffix = suffix_map.get(process_type, 'unknown')

            # Extract common params for decide_filepath
            dir_rule_dict = actual_params.get('dir_rule')
            filename_rule = actual_params.get('filename_rule')

            output_path = "unknown"
            is_directory = False

            # Special case for Zip photo level (multiple files)
            if process_type == 'zip' and actual_params.get('level', 'photo') == 'photo':
                first_photo = next(iter(photo_dict.keys()))
                # Plugin ignore base_dir if dir_rule_dict is present
                sample_path = plugin.decide_filepath(album, first_photo, filename_rule, suffix, None, dir_rule_dict)
                output_path = str(Path(sample_path).parent.resolve())
                is_directory = True
            else:
                raw_path = plugin.decide_filepath(album, None, filename_rule, suffix, None, dir_rule_dict)
                output_path = str(Path(raw_path).resolve())

            self.logger.info(f"Post-process '{process_type}' finished. Output: {output_path}")
            return {
                "status": "success",
                "process_type": process_type,
                "album_id": album_id,
                "output_path": output_path,
                "is_directory": is_directory,
                "message": f"Post-process '{process_type}' completed successfully."
            }

        except Exception as e:
            self.logger.exception("Post-process failed")
            return {
                "status": "error",
                "album_id": album_id,
                "process_type": process_type,
                "output_path": "",
                "is_directory": False,
                "message": f"Post-process failed: {e}"
            }
