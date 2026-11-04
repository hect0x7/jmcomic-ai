# JmOption Reference

Complete reference for configuring `jmcomic` behavior.

## Top Level Fields

- **`version`**: Configuration version string (`"2.1"` recommended; backward-compatible with `"2.0"`)
- **`log`**: Boolean or `"pretty"` (default: `true`). JMComic AI enforces file-only logging even when `"pretty"` is set so MCP `stdio` JSON-RPC never receives stdout/stderr log pollution.
- **`dir_rule`**: Directory and file naming rules
- **`download`**: Download behavior configuration
- **`client`**: Network client configuration (domains, retry, proxies, async client)
- **`auth`**: Account credentials and session cookies (recommended in `v2.1`)
- **`plugins`**: Plugin configurations

---

## dir_rule

Controls where and how files are saved.

### Fields

- **`base_dir`**: Root directory for downloads
  - Supports environment variables: `${JM_DIR}/downloads/`
  - Example: `D:/downloads/jmcomic/`

- **`rule`**: Directory structure DSL
  - Start with `Bd` (base directory)
  - Use `/` or `_` to separate levels
  - Use `Pxxx` for photo properties, `Axxx` for album properties
  - Supports f-string syntax: `Bd / Aauthor / (JM{Aid}-{Pindex})-{Pname}`
  - Default: `Bd / Ptitle`
  - Examples:
    - `Bd / Ptitle` - Root / Chapter Title
    - `Bd / Aid / Pindex` - Root / Album ID / Chapter Index
    - `Bd / Aauthor / (JM{Aid}-{Pindex})-{Pname}` - Root / Author / (JM123-1)-ChapterName

- **`normalize_zh`**: Chinese character normalization (optional)
  - `null` (default): No conversion
  - `zh-cn`: Convert to simplified Chinese
  - `zh-tw`: Convert to traditional Chinese
  - Requires `zhconv` library

### Example

```yaml
dir_rule:
  base_dir: D:/downloads/jmcomic/
  rule: Bd / Aauthor / Ptitle
  normalize_zh: zh-cn
```

---

## download

Download behavior settings.

### Fields

- **`cache`**: Boolean, skip downloading existing files (default: true)

- **`image`**: Image download settings
  - **`decode`**: Boolean, decode scrambled images (default: true)
  - **`suffix`**: String or null, force image format (e.g., `.jpg`, `.png`)

- **`threading`**: Concurrency settings
  - **`image`**: Integer, max concurrent image downloads (positive integer, default: 20)
  - **`photo`**: Integer, max concurrent chapter downloads (default: CPU thread count)

### Example

```yaml
download:
  cache: true
  image:
    decode: true
    suffix: .jpg
  threading:
    image: 20
    photo: 16
```

---

## client

Network client configuration.

### Fields

- **`impl`**: Client implementation type
  - `html`: Web client (IP restricted but efficient)
  - `api`: APP client (no IP restriction, better compatibility)

- **`async_impl`**: Native async client implementation
  - `null` (default): Automatically follows `impl` (`api` → `async_api`, `html` → `async_html`)
  - `async_api` (or `api`): Force async APP API client
  - `async_html` (or `html`): Force async Web HTML client
  - Used by upstream `_async` APIs such as `download_album_async`

- **`cache`**: Metadata cache scope for album details, searches, and other client requests
  - `null` or `false`: Disable client metadata caching (default)
  - `true` or `level_option`: Share one cache across clients created from the same option
  - `level_client`: Keep an independent cache for each client

- **`domain`**: Domain configuration for different implementations
  - **`html`**: Array of domains for HTML client
    - Example: `["18comic.vip", "18comic.org"]`
  - **`api`**: Array of domains for API client
    - Example: `["www.jmapiproxyxxx.vip"]`

- **`retry_times`**: Integer, number of retry attempts on failure (default: 5)

- **`postman`**: Request configuration
  - **`type`**: HTTP backend implementation (default: `cffi`)
  - **`meta_data`**: Metadata for requests
    - **`impersonate`**: Browser TLS fingerprint (default: `chrome110`)
    - **`proxies`**: Proxy configuration
      - `null`: No proxy
      - `system`: Use system proxy (default)
      - `clash`: Use Clash proxy
      - `v2ray`: Use V2Ray proxy
      - `127.0.0.1:7890`: Custom proxy address
      - Object with `http` and `https` keys for detailed config
    - **`cookies`**: Legacy login cookies (optional; top-level `auth.cookies` is preferred in `v2.1` and takes precedence when both are set)
      - **`AVS`**: AVS cookie value from browser
      - **Important**: Cookies must match the domain being accessed

### Example

```yaml
client:
  impl: html
  async_impl: null  # Auto-follows impl -> async_html
  cache: null
  domain:
    html:
      - 18comic.vip
      - 18comic.org
    api:
      - www.jmapiproxyxxx.vip
  retry_times: 5
  postman:
    meta_data:
      proxies: system
      # Or custom proxy:
      # proxies:
      #   http: 127.0.0.1:7890
      #   https: 127.0.0.1:7890
```

---

## auth

Top-level account authentication settings introduced in `option v2.1` (`jmcomic >= 2.7.11`).

### Fields

- **`username`**: JMComic account username (`string` or `null`)
  - Supports `${ENV_VAR}` placeholders (e.g., `${JM_USERNAME}`). Unset environment variables resolve to `null` at runtime rather than a literal `"${...}"` string.
- **`password`**: JMComic account password (`string` or `null`)
  - Supports `${ENV_VAR}` placeholders (e.g., `${JM_PASSWORD}`). `update_option` preserves `${ENV_VAR}` placeholders on disk without writing expanded plaintext secrets.
  - When both `username` and `password` are present, JMComic AI lazily authenticates on the first client request or download (never eagerly during server startup or offline `plan_download`).
- **`cookies`**: Session cookies mapping (optional, e.g., `AVS`)
  - Takes priority over legacy `client.postman.meta_data.cookies` when both are configured.
  - Choose **either** `username`/`password` (recommended, works for both `api` and `html`) **or** `cookies` (browser `AVS` cookies apply to `html`). Do not configure both simultaneously: on `impl: html`, existing `cookies` + `username` marks the session as already logged in and skips re-login if the cookie expires.

### Example

```yaml
auth:
  username: "${JM_USERNAME}"
  password: "${JM_PASSWORD}"
  # Or cookie-only authentication:
  # cookies:
  #   AVS: "${JM_COOKIE_AVS}"
```

---

## plugins

Plugin configurations. Plugins execute at different lifecycle stages.

### Policy Settings

- **`valid`**: Parameter validation failure strategy (`log` default, `ignore`, or `raise`)
- **`dependencies_strategy`**: Optional third-party dependency check strategy (`failed-fast` default, `auto-install`, or `ignore-only-log`)

### Lifecycle Stages

- **`after_init`**: After initialization
- **`before_album`**: Before downloading an album
- **`after_album`**: After downloading an album
- **`before_photo`**: Before downloading a chapter
- **`after_photo`**: After downloading a chapter
- **`before_image`**: Before downloading an image
- **`after_image`**: After downloading an image
- **`main`**: Main execution

### Common Plugins

#### `usage_log` (after_init)
Monitor hardware usage.
```yaml
- plugin: usage_log
  kwargs:
    interval: 0.5
    enable_warning: true
```

#### `download_progress` (after_init, interactive terminal only)
Show the upstream Rich album/chapter progress UI and write complete logs to a file.
```yaml
- plugin: download_progress
  kwargs:
    log_file: jmcomic-download.log
    terminal_log_lines: 6
```

Use this only for direct interactive-terminal workflows. Do not enable it for `jmai` MCP/stdio
downloads, which already report progress through MCP Context and return an isolated task log.

#### `login` (after_init, legacy / force re-login)
Force an immediate login and write cookies back to `option.auth`. Prefer top-level `auth` (`username` / `password`) for lazy on-demand login in `v2.1`. When `auth` is already configured, `username` and `password` in `kwargs` may be omitted.
```yaml
- plugin: login
  kwargs:
    username: ${JM_USERNAME}
    password: ${JM_PASSWORD}
```

#### `download_cover` (before_album)
Download album covers.
```yaml
- plugin: download_cover
  kwargs:
    size: '_3x4'  # Optional, for search page size
    dir_rule:
      base_dir: D:/covers/
      rule: '{Atitle}/{Aid}_cover.jpg'
```

#### `zip` (after_album or after_photo)
Compress downloaded files. Archive granularity is inferred automatically from the lifecycle stage (`after_album` packs the whole album; `after_photo` packs each chapter); explicit `level` in `option.yml` is deprecated.
```yaml
- plugin: zip
  kwargs:
    suffix: zip   # or '7z'
    delete_original_file: true
    encrypt:
      type: random  # or specify password
```

#### `calibre_metadata` (after_album)
Generate a Calibre `metadata.opf` sidecar file (and optional `cover.jpg`) for the downloaded album (requires optional `jmcomic-calibre` package).
```yaml
- plugin: calibre_metadata
  kwargs:
    dir_rule:
      base_dir: D:/downloads/jmcomic/
      rule: 'Bd/{Aid}/metadata.opf'
    include_cover: true
    fields:
      language: zh
```

#### `img2pdf` (after_photo or after_album)
Merge images into PDF.
```yaml
- plugin: img2pdf
  kwargs:
    pdf_dir: D:/pdf/
    filename_rule: Pid  # Use Axxx for after_album
    encrypt:
      password: "123456"
```

#### `send_qq_email` (after_album)
Send email notification.
```yaml
- plugin: send_qq_email
  kwargs:
    msg_from: sender@qq.com
    msg_to: recipient@qq.com
    password: authorization_code
    title: Download Complete
    content: Your download has finished!
```

### Example

```yaml
plugins:
  after_init:
    - plugin: usage_log
      kwargs:
        interval: 0.5
        enable_warning: true

  before_album:
    - plugin: download_cover
      kwargs:
        dir_rule:
          base_dir: D:/covers/
          rule: '{Atitle}/{Aid}_cover.jpg'

  after_photo:
    - plugin: zip
      kwargs:
        suffix: zip
        delete_original_file: true

  after_album:
    - plugin: send_qq_email
      kwargs:
        msg_from: ${EMAIL}
        msg_to: recipient@qq.com
        password: ${EMAIL_PASSWORD}
        title: Download Complete
        content: Album downloaded successfully!
```

---

## Environment Variables

Top-level `auth`, `dir_rule.base_dir`, and plugin `kwargs` parameters support environment variable references using `${VAR_NAME}` syntax.

Example:
```yaml
dir_rule:
  base_dir: ${JM_DOWNLOAD_DIR}/

auth:
  username: ${JM_USERNAME}
  password: ${JM_PASSWORD}
  # Or cookie-based auth:
  # cookies:
  #   AVS: ${JM_COOKIE_AVS}

plugins:
  after_album:
    - plugin: send_qq_email
      kwargs:
        msg_from: ${EMAIL}
        password: ${EMAIL_PASSWORD}
```

---

## Complete Example

```yaml
version: "2.1"
log: true

dir_rule:
  base_dir: D:/downloads/jmcomic/
  rule: Bd / Aauthor / Ptitle
  normalize_zh: zh-cn

download:
  cache: true
  image:
    decode: true
    suffix: .jpg
  threading:
    image: 20
    photo: 16

client:
  impl: html
  async_impl: null
  cache: level_option
  domain:
    html:
      - 18comic.vip
      - 18comic.org
  retry_times: 5
  postman:
    meta_data:
      proxies: system

auth:
  username: ${JM_USERNAME}
  password: ${JM_PASSWORD}

plugins:
  after_init:
    - plugin: usage_log
      kwargs:
        interval: 0.5
        enable_warning: true

  after_photo:
    - plugin: zip
      kwargs:
        suffix: zip
        delete_original_file: true
        encrypt:
          type: random
```

---

For the complete list of plugins and their parameters, see `assets/option_schema.json`.
