# JmOption Reference

Complete reference for configuring `jmcomic` behavior.

## Top Level Fields

- **`version`**: Configuration version string (e.g., "2.0")
- **`log`**: Boolean, whether to enable console logging (default: true)
- **`dir_rule`**: Directory and file naming rules
- **`download`**: Download behavior configuration
- **`client`**: Network client configuration (domains, retry, proxies, cookies)
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
  - **`image`**: Integer, max concurrent image downloads (default: 30, max: 50)
  - **`photo`**: Integer, max concurrent chapter downloads (default: CPU thread count)

### Example

```yaml
download:
  cache: true
  image:
    decode: true
    suffix: .jpg
  threading:
    image: 30
    photo: 16
```

---

## client

Network client configuration.

### Fields

- **`impl`**: Client implementation type
  - `html`: Web client (IP restricted but efficient)
  - `api`: APP client (no IP restriction, better compatibility)

- **`domain`**: Domain configuration for different implementations
  - **`html`**: Array of domains for HTML client
    - Example: `["18comic.vip", "18comic.org"]`
  - **`api`**: Array of domains for API client
    - Example: `["www.jmapiproxyxxx.vip"]`

- **`retry_times`**: Integer, number of retry attempts on failure (default: 5)

- **`postman`**: Request configuration
  - **`meta_data`**: Metadata for requests
    - **`proxies`**: Proxy configuration
      - `null`: No proxy
      - `system`: Use system proxy (default)
      - `clash`: Use Clash proxy
      - `v2ray`: Use V2Ray proxy
      - `127.0.0.1:7890`: Custom proxy address
      - Object with `http` and `https` keys for detailed config
    - **`cookies`**: Login cookies (optional)
      - **`AVS`**: AVS cookie value from browser
      - **Important**: Cookies must match the domain being accessed

### Example

```yaml
client:
  impl: html
  domain:
    html:
      - 18comic.vip
      - 18comic.org
    api:
      - www.jmapiproxyxxx.vip
  retry_times: 5
  postman:
    meta_data:
      # Proxy options:
      proxies: system
      # Or custom proxy:
      # proxies:
      #   http: 127.0.0.1:7890
      #   https: 127.0.0.1:7890

      # Login cookies (optional):
      cookies:
        AVS: your_avs_cookie_value
```

---

## plugins

Plugin configurations. Plugins execute at different lifecycle stages.

### Lifecycle Stages

- **`after_init`**: After initialization
- **`before_album`**: Before downloading an album
- **`after_album`**: After downloading an album
- **`before_photo`**: Before downloading a chapter
- **`after_photo`**: After downloading a chapter
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

#### `login` (after_init)
Login with username and password.
```yaml
- plugin: login
  kwargs:
    username: your_username
    password: your_password
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

#### `zip` (after_album)
Compress downloaded files.
```yaml
- plugin: zip
  kwargs:
    level: photo  # or 'album'
    suffix: zip   # or '7z'
    delete_original_file: true
    encrypt:
      type: random  # or specify password
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

  after_album:
    - plugin: zip
      kwargs:
        level: photo
        suffix: zip
        delete_original_file: true

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

All `kwargs` parameters support environment variable references using `${VAR_NAME}` syntax.

Example:
```yaml
dir_rule:
  base_dir: ${JM_DOWNLOAD_DIR}/

client:
  postman:
    meta_data:
      cookies:
        AVS: ${JM_COOKIE_AVS}

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
version: "2.0"
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
    image: 30
    photo: 16

client:
  impl: html
  domain:
    html:
      - 18comic.vip
      - 18comic.org
  retry_times: 5
  postman:
    meta_data:
      proxies: system
      cookies:
        AVS: your_avs_cookie_value

plugins:
  after_init:
    - plugin: usage_log
      kwargs:
        interval: 0.5
        enable_warning: true

  after_album:
    - plugin: zip
      kwargs:
        level: photo
        suffix: zip
        delete_original_file: true
        encrypt:
          type: random
```

---

For the complete list of plugins and their parameters, see `option_schema.json`.
