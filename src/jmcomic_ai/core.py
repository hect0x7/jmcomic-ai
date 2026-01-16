import logging
import os
import sys
from pathlib import Path
from typing import Any

from jmcomic import (
    JmAlbumDetail,
    JmCategoryPage,
    JmcomicClient,
    JmcomicText,
    JmMagicConstants,
    JmModuleConfig,
    JmOption,
    JmPageContent,
    JmSearchPage,
    create_option_by_file,
)



ENV_OPTION_PATH = "JM_OPTION_PATH"
DEFAULT_OPTION_PATH = Path.home() / ".jmcomic" / "option.yml"


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
    def __init__(self, option_path: str | None = None):
        self._setup_logging()
        self.option_path = resolve_option_path(option_path, self.logger)
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

    def _setup_logging(self):
        """Setup logging to both file and console"""
        log_file = Path.cwd() / "jmcomic_ai.log"
        self.logger = logging.getLogger("jmcomic_ai")
        self.logger.setLevel(logging.INFO)
        
        # 1. Ensure Root Logger has basic configuration (for 3rd party libs like mcp, uvicorn, jmcomic)
        # We use a formatter similar to what was there before
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            root_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            # Root File Handler
            try:
                root_file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
                root_file_handler.setFormatter(root_formatter)
                root_logger.addHandler(root_file_handler)
                root_logger.setLevel(logging.INFO)
            except Exception:
                pass # Fallback for read-only filesystems in CI

        # 2. Configure jmcomic_ai named logger (for nicer CLI output)
        # Check if a StreamHandler already exists to avoid duplicate handlers
        has_console_handler = any(
            isinstance(handler, logging.StreamHandler) and getattr(handler, 'stream', None) in (sys.stderr, sys.stdout)
            for handler in self.logger.handlers
        )
        
        if not has_console_handler:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter("[*] %(message)s")
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # Ensure our named logger doesn't propagate to root if handlers are present on both 
        # but in our case we WANT it to go to file (via root) and stderr (via self).
        # To avoid double printing in file, we check if root already has a file handler.
        
        self.logger.info(f"Logging to file: {log_file}")
        sys.stderr.flush()

    def reload_option(self):
        """
        [not a tool]
        """
        self.option = self._load_option()

    def update_option(self, option_updates: dict[str, Any]) -> str:
        """
        Update JMComic option and save to file.

        This tool updates the JMComic option with the provided settings,
        validates the new option, and persists it to the option file.

        Args:
            option_updates: Dictionary containing option updates to merge.
                           Supports nested updates for client, download, dir_rule, etc.

        Returns:
            Success message with file path, or error message if validation fails.

        Example:
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
            self.option = new_option

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

        # 使用 jmcomic 提供的迭代器获取 id, title, tags
        for album_id, title, tags in page.iter_id_title_tag():
            album_id = str(album_id)
            albums.append(
                {
                    "id": album_id,
                    "title": str(title),
                    "tags": tags,
                    "cover_url": JmcomicText.get_album_cover_url(album_id),
                }
            )

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
            "category": "0",  # JmAlbumDetail does not have a category field
            "tags": album.tags,
            "actors": album.actors,
            "description": str(album.description),
            "chapter_count": len(album),
            "update_time": str(album.update_date),
            "cover_url": JmcomicText.get_album_cover_url(album.album_id),
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
        Search for albums/comics with advanced filtering options.

        Args:
            keyword: Search query string (supports album ID, title, author, tags, etc.)
            page: Page number, starting from 1 (default: 1)
            main_tag: Search scope - 0 (站内), 1 (作品), 2 (作者), 3 (标签), 4 (角色) (default: 0)
            order_by: Sort order - 网页: mr (最新), mv (观看), mp (图片), tf (点赞); API: time, views, likes (default: "latest")
            time_range: Time filter - all (全部), today (今天), week (本周), month (本月) (default: "all")
            category: Category filter - "all" or specific category CID (default: "all")

        Returns:
            Dictionary containing:
                - albums: List of album dictionaries
                - total_count: Total number of results
        """
        client = self.get_client()

        # Call core search method
        search_page: JmSearchPage = client.search(
            keyword,
            page=page,
            main_tag=main_tag,
            order_by=order_by,
            time=time_range,
            category=category,
            sub_category=None,
        )

        self.logger.info(f"Search finished: keyword={keyword}, results={len(search_page)}")
        return self._parse_search_page(search_page)

    def get_ranking(self, period: str = "day", page: int = 1) -> dict[str, Any]:
        """
        Get trending/popular albums from ranking lists.

        Args:
            period: Ranking period - "day" (日榜), "week" (周榜), "month" (月榜) (default: "day")
            page: Page number, starting from 1 (default: 1)

        Returns:
            Dictionary containing:
                - albums: List of ranked album dictionaries
                - total_count: Total number of results
        """
        client = self.get_client()
        search_page: JmCategoryPage
        if period == "day":
            search_page = client.day_ranking(page)
        elif period == "week":
            search_page = client.week_ranking(page)
        elif period == "month":
            search_page = client.month_ranking(page)
        else:
            return {"albums": [], "total_count": 0}

        return self._parse_search_page(search_page)

    async def download_album(self, album_id: str) -> str:
        """
        Download an entire album/comic in the background.

        This is a non-blocking operation that starts the download task asynchronously.
        The actual download happens in the background and logs progress to jmcomic_ai.log.

        Args:
            album_id: The album ID to download (e.g., "123456")

        Returns:
            Confirmation message that download has started, including the expected download path.
        """
        import asyncio

        # 1. Get album metadata to predict download path
        album = self.get_client().get_album_detail(album_id)
        # Use native library method to decide the root directory
        target_path = self.option.dir_rule.decide_album_root_dir(album)

        def _bg_download():
            try:
                self.logger.info(f"Starting download for album {album_id} to {target_path}")
                self.option.download_album(album_id)
                self.logger.info(f"Download completed for album {album_id}")
            except Exception as e:
                self.logger.error(f"Download failed for album {album_id}: {str(e)}")

        # 使用 asyncio.create_task 将下载任务提交到后台执行
        asyncio.create_task(asyncio.to_thread(_bg_download))

        return f"Download started for album {album_id}. Expected path: {target_path}"

    def download_photo(self, photo_id: str) -> str:
        """
        Download a specific chapter/photo from an album.

        Args:
            photo_id: The chapter/photo ID to download (e.g., "123456")

        Returns:
            Confirmation message that download has started.
        """
        self.option.download_photo(photo_id)
        return f"Download started for photo {photo_id}"

    def login(self, username: str, password: str) -> str:
        """
        Authenticate with JMComic account to access premium features.

        Login is required to access favorite lists, premium content, and user-specific features.
        Session cookies are automatically saved for subsequent requests.

        Args:
            username: JMComic account username
            password: JMComic account password

        Returns:
            Success message with username, or error message if login fails.
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
        Retrieve comprehensive details about a specific album/comic.

        Args:
            album_id: The album ID (e.g., "123456")

        Returns:
            Album dictionary containing: id, title, author, likes, views, category,
            tags, actors, description, chapter_count, update_time, cover_url.
        """
        client = self.get_client()
        album = client.get_album_detail(album_id)
        return self._parse_album_detail(album)

    def get_category_list(
        self,
        category: str = JmMagicConstants.CATEGORY_ALL,
        page: int = 1,
        sort_by: str = JmMagicConstants.ORDER_BY_LATEST,
    ) -> dict[str, Any]:
        """
        Browse albums by category with sorting options.

        Args:
            category: Category filter. Available categories:
                - "0" or CATEGORY_ALL: 全部 (All)
                - "doujin" or CATEGORY_DOUJIN: 同人 (Doujin)
                - "single" or CATEGORY_SINGLE: 单本 (Single Volume)
                - "short" or CATEGORY_SHORT: 短篇 (Short Story)
                - "another" or CATEGORY_ANOTHER: 其他 (Other)
                - "hanman" or CATEGORY_HANMAN: 韩漫 (Korean Comics)
                - "meiman" or CATEGORY_MEIMAN: 美漫 (American Comics)
                - "doujin_cosplay" or CATEGORY_DOUJIN_COSPLAY: Cosplay
                - "3D" or CATEGORY_3D: 3D
                - "english_site" or CATEGORY_ENGLISH_SITE: 英文站 (English Site)
                (default: "0")
            page: Page number, starting from 1 (default: 1)
            sort_by: Sort order. Available options:
                - "mr" or ORDER_BY_LATEST: 最新 (Latest)
                - "mv" or ORDER_BY_VIEW: 观看数 (Most Viewed)
                - "mp" or ORDER_BY_PICTURE: 图片数 (Most Pictures)
                - "tf" or ORDER_BY_LIKE: 点赞数 (Most Liked)
                (default: "mr")

        Returns:
            Dictionary containing:
                - albums: List of album dictionaries matching the criteria
                - total_count: Total number of results
        """
        client = self.get_client()

        search_page: JmCategoryPage = client.categories_filter(
            page=page, time=JmMagicConstants.TIME_ALL, category=category, order_by=sort_by, sub_category=None
        )
        return self._parse_search_page(search_page)

    def download_cover(self, album_id: str) -> str:
        """
        Download the cover image of a specific album.

        The cover image is saved to the 'covers' subdirectory within the configured base directory.

        Args:
            album_id: The album ID (e.g., "123456")

        Returns:
            Success message with the saved file path.
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

    def post_process(self, album_id: str, process_type: str, params: dict[str, Any] | None = None) -> str:
        """
        Perform post-processing (Zip, PDF, LongImage) on an already downloaded album.

        This tool leverages jmcomic's native plugin system to process downloaded comic files.
        It is thread-safe and does not modify the global configuration.

        Args:
            album_id: The ID of the album to process.
            process_type: The type of processing to perform. Options: "zip", "img2pdf", "long_img".
            params: Optional dictionary of parameters for the specific plugin.

        Returns:
            Success or error message.
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
                photo_dir = self.option.decide_image_save_dir(photo)
                if not os.path.exists(photo_dir):
                    continue
                
                images = []
                for file in sorted(os.listdir(photo_dir)):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')) and not file.startswith('.'):
                        images.append((os.path.join(photo_dir, file), None))
                
                if images:
                    photo_dict[photo] = images
                    total_images += len(images)
            
            if not photo_dict:
                return f"Error: No downloaded images found for album {album_id}. Expected path: {self.option.dir_rule.decide_album_root_dir(album)}"
            
            mock_downloader.download_success_dict[album] = photo_dict
            self.logger.info(f"Found {len(photo_dict)} chapters and {total_images} images for post-processing.")

            # 3. Safe Plugin Invocaton (No pollution to self.option)
            pclass = JmModuleConfig.REGISTRY_PLUGIN.get(process_type)
            if pclass is None:
                return f"Error: Plugin '{process_type}' not found."

            # Construct actual params
            actual_params = params.copy() if params else {}
            if 'filename_rule' not in actual_params:
                actual_params['filename_rule'] = 'Aid'
            
            # Add required engine data for the plugin
            actual_params.update({
                'album': album,
                'downloader': mock_downloader
            })

            # Instantiate and invoke
            plugin = pclass.build(self.option)
            plugin.invoke(**actual_params)

            self.logger.info(f"Post-process '{process_type}' finished for album {album_id}")
            return f"Post-process '{process_type}' completed successfully for album {album_id}."

        except Exception as e:
            self.logger.error(f"Post-process failed: {str(e)}")
            return f"Post-process failed: {str(e)}"
