# JMComic Option Configuration Examples

This file contains various configuration examples for JMComic-Crawler-Python.

## Minimal Configuration

```yaml
# Minimal config - uses all defaults
log: true
```

## Basic Download Configuration

```yaml
version: "2.0"
log: true

# Set download directory
dir_rule:
  base_dir: D:/downloads/jmcomic/
  rule: Bd / Ptitle

# Basic download settings
download:
  cache: true
  image:
    decode: true
  threading:
    image: 30
    photo: 5
```

## Configuration with Proxy

```yaml
version: "2.0"
log: true

dir_rule:
  base_dir: D:/downloads/jmcomic/

# Use system proxy
client:
  postman:
    meta_data:
      proxies: system

# Or use custom proxy
# client:
#   postman:
#     meta_data:
#       proxies:
#         http: 127.0.0.1:7890
#         https: 127.0.0.1:7890
```

## Configuration with Login

```yaml
version: "2.0"
log: true

dir_rule:
  base_dir: D:/downloads/jmcomic/

# Login with cookies
client:
  postman:
    meta_data:
      proxies: system
      cookies:
        AVS: your_avs_cookie_value_from_browser

# Or use login plugin
plugins:
  after_init:
    - plugin: login
      kwargs:
        username: your_username
        password: your_password
```

## Advanced Directory Rules

```yaml
version: "2.0"

dir_rule:
  base_dir: ${JM_DOWNLOAD_DIR}/
  # Save as: BaseDir / Author / (JM123-1)-ChapterName
  rule: Bd / Aauthor / (JM{Aid}-{Pindex})-{Pname}
  normalize_zh: zh-cn  # Convert to simplified Chinese

download:
  threading:
    image: 30
    photo: 16
```

## Configuration with Plugins

```yaml
version: "2.0"
log: true

dir_rule:
  base_dir: D:/downloads/jmcomic/

download:
  cache: true
  threading:
    image: 30
    photo: 5

plugins:
  # Monitor hardware usage
  after_init:
    - plugin: usage_log
      kwargs:
        interval: 0.5
        enable_warning: true

  # Download album covers
  before_album:
    - plugin: download_cover
      kwargs:
        dir_rule:
          base_dir: D:/covers/
          rule: '{Atitle}/{Aid}_cover.jpg'

  # Compress and notify after download
  after_album:
    - plugin: zip
      kwargs:
        level: photo
        suffix: zip
        delete_original_file: true
        encrypt:
          type: random

    - plugin: send_qq_email
      kwargs:
        msg_from: ${EMAIL}
        msg_to: recipient@qq.com
        password: ${EMAIL_PASSWORD}
        title: Download Complete
        content: Album downloaded successfully!
```

## PDF Generation Configuration

```yaml
version: "2.0"

dir_rule:
  base_dir: D:/downloads/jmcomic/

plugins:
  # Merge each chapter into a PDF
  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: D:/pdf/
        filename_rule: Pid
        encrypt:
          password: "123456"

  # Or merge entire album into one PDF
  # after_album:
  #   - plugin: img2pdf
  #     kwargs:
  #       pdf_dir: D:/pdf/
  #       filename_rule: Aname
  #       encrypt:
  #         password: "123456"
```

## Multi-Domain Configuration

```yaml
version: "2.0"

client:
  impl: html
  # Try multiple domains in order
  domain:
    html:
      - 18comic.vip
      - 18comic.org
      - 18comic.biz
    api:
      - www.jmapiproxyxxx.vip
  retry_times: 5
  postman:
    meta_data:
      proxies: system
```

## Skip Low-Quality Chapters

```yaml
version: "2.0"

dir_rule:
  base_dir: D:/downloads/jmcomic/

plugins:
  # Skip chapters with less than 3 images (usually announcements)
  before_photo:
    - plugin: skip_photo_with_few_images
      kwargs:
        at_least_image_count: 3
```

## Auto-Update Subscription

```yaml
version: "2.0"

dir_rule:
  base_dir: D:/downloads/jmcomic/

plugins:
  after_init:
    # Only download new chapters
    - plugin: find_update
      kwargs:
        145504: 290266  # Album 145504, last downloaded chapter 290266
        234567: 345678  # Album 234567, last downloaded chapter 345678

    # Subscribe to updates and send email
    - plugin: subscribe_album_update
      kwargs:
        download_if_has_update: true
        email_notify:
          msg_from: ${EMAIL}
          msg_to: ${EMAIL}
          password: ${EMAIL_PASSWORD}
          title: New Chapter Available!
          content: Your subscribed album has new chapters!
        album_photo_dict:
          324930: 424507
```

## Complete Production Configuration

```yaml
version: "2.0"
log: true

# Directory configuration
dir_rule:
  base_dir: ${JM_DOWNLOAD_DIR}/
  rule: Bd / Aauthor / (JM{Aid}-{Pindex})-{Pname}
  normalize_zh: zh-cn

# Download settings
download:
  cache: true
  image:
    decode: true
    suffix: .jpg
  threading:
    image: 30
    photo: 16

# Client configuration
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
        AVS: ${JM_COOKIE_AVS}

# Plugins
plugins:
  after_init:
    # Monitor system resources
    - plugin: usage_log
      kwargs:
        interval: 0.5
        enable_warning: true

    # Only download new chapters
    - plugin: find_update
      kwargs:
        145504: 290266

  before_album:
    # Download covers
    - plugin: download_cover
      kwargs:
        dir_rule:
          base_dir: ${JM_DOWNLOAD_DIR}/covers/
          rule: '{Atitle}/{Aid}_cover.jpg'

  before_photo:
    # Skip announcement chapters
    - plugin: skip_photo_with_few_images
      kwargs:
        at_least_image_count: 3

  after_photo:
    # Merge into PDF
    - plugin: img2pdf
      kwargs:
        pdf_dir: ${JM_DOWNLOAD_DIR}/pdf/
        filename_rule: Pid
        encrypt:
          password: ${PDF_PASSWORD}

  after_album:
    # Compress with encryption
    - plugin: zip
      kwargs:
        level: photo
        suffix: 7z
        dir_rule:
          base_dir: ${JM_DOWNLOAD_DIR}/archives/
          rule: 'Bd / {Atitle} / [{Pid}]-{Ptitle}.7z'
        delete_original_file: true
        encrypt:
          impl: 7z
          type: random

    # Send completion email
    - plugin: send_qq_email
      kwargs:
        msg_from: ${EMAIL}
        msg_to: ${EMAIL}
        password: ${EMAIL_PASSWORD}
        title: JMComic Download Complete
        content: Album downloaded, compressed, and archived successfully!
```

## Notes

1. **Environment Variables**: Use `${VAR_NAME}` syntax to reference environment variables
2. **Directory Rules**:
   - `Bd` = Base Directory
   - `Axxx` = Album properties (e.g., `Aid`, `Atitle`, `Aauthor`)
   - `Pxxx` = Photo/Chapter properties (e.g., `Pid`, `Ptitle`, `Pindex`)
3. **Proxy Settings**: Must be under `client.postman.meta_data.proxies`
4. **Cookies**: Must be under `client.postman.meta_data.cookies`
5. **Plugin Lifecycle**: Choose the right stage for each plugin
6. **Compression**: Use `7z` with `impl: 7z` for maximum privacy (encrypts file headers)
