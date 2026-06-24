# CampusCrawler

面向大学生和研究生的公开校园信息采集助手。

CampusCrawler 在本地运行，用于从高校公开网页中查找并整理：

- 学校标识：Logo、校徽、视觉识别素材
- 校园通知：通知、公告、公示、讲座与竞赛信息
- 招生信息：招生简章、专业目录、复试与调剂信息

> 本项目只采集无需登录即可正常访问的公开网页。它不会绕过登录、验证码、访问控制、限速或其他技术保护。

## 快速开始

需要 Python 3.10 或更高版本，不需要安装第三方运行依赖。

```powershell
python app.py
```

浏览器将自动打开：

```text
http://127.0.0.1:8765
```

Windows 用户也可以双击 `start_campus_crawler.bat`。

## 使用方法

1. 选择学校标识、校园通知或招生信息。
2. 输入学校官网或具体栏目网址。
3. 设置最多访问的页面数，然后开始采集。
4. 检查原始链接，并导出 CSV、JSON 或 Markdown。

下载和导出文件保存在程序旁边的 `downloads/` 目录。

## Windows 打包

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

生成文件：`dist\CampusCrawler.exe`

## 合规原则

- 仅访问公开网页，并遵守网站的 `robots.txt`。
- 默认限制访问页数，并在页面间保留请求间隔。
- 不绕过登录、验证码、付费墙、IP 限制或访问控制。
- 不使用未授权账号、Cookie、Token、私有接口或泄露数据。
- 网站拒绝访问或明确禁止自动采集时立即停止。
- 使用者仍需自行遵守当地法律、网站条款、版权和隐私要求。

详见 [SECURITY.md](SECURITY.md)。

## 项目结构

```text
app.py                 本地 HTTP 服务
campus_crawler.py      采集、合规检查、下载和导出核心
web/                   本地网页界面
tests/                 自动测试
build_exe.ps1          Windows 打包脚本
```

## 开发

```powershell
python -m unittest discover -s tests -v
```

贡献代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 当前限制

- 不执行必须依赖浏览器 JavaScript 才能生成的内容。
- 通用规则无法保证适配所有高校网站。
- 日期和栏目识别依赖网页文字与链接结构，结果需要人工核对。
- 当前版本不是后台监控服务，不会定时自动采集。

## License

[MIT](LICENSE)
