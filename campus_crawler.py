from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


APP_NAME = "CampusCrawler"
USER_AGENT = "CampusCrawler/0.2 (+local public-information research tool)"
ASSET_EXTENSIONS = {
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
    ".zip", ".rar", ".7z", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}
IMAGE_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
COLLECTOR_KEYWORDS = {
    "logo": ("logo", "brand", "identity", "seal", "badge", "emblem", "校徽", "标识", "视觉识别", "学校概况"),
    "notice": ("通知", "公告", "新闻", "公示", "讲座", "竞赛", "奖学金", "notice", "news"),
    "admission": ("招生", "研究生", "硕士", "博士", "复试", "调剂", "专业目录", "招生简章", "admission", "graduate"),
}
DATE_RE = re.compile(r"(20\d{2})[年./-]\s*(\d{1,2})[月./-]\s*(\d{1,2})日?")


@dataclass
class ResultItem:
    title: str
    category: str
    url: str
    source_page: str
    date: str = ""
    department: str = ""
    file_type: str = ""
    score: int = 0
    reason: str = ""
    preview_url: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.assets: list[dict[str, str]] = []
        self.title = ""
        self._anchor: dict[str, str] | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag == "a" and values.get("href"):
            self._anchor = {"href": values["href"], "text": "", "title": values.get("title", "")}
            self.links.append(self._anchor)
        if tag in {"img", "source"}:
            src = values.get("src") or values.get("data-src") or values.get("srcset")
            if src:
                self.assets.append({
                    "href": src.split(",", 1)[0].strip().split(" ", 1)[0],
                    "text": values.get("alt", "") or values.get("title", ""),
                })
        if tag == "link":
            rel = values.get("rel", "").lower()
            if values.get("href") and "icon" in rel:
                self.assets.append({"href": values["href"], "text": rel})

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._anchor = None
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = compact_text(data)
        if self._anchor is not None and text:
            self._anchor["text"] += (" " if self._anchor["text"] else "") + text
        if self._in_title and text:
            self.title += (" " if self.title else "") + text


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("请输入学校官网或栏目页面地址。")
    if not re.match(r"^https?://", value, re.I):
        value = f"https://{value}"
    parsed = urllib.parse.urlsplit(value)
    if not parsed.netloc:
        raise ValueError("网址格式不正确，例如：https://www.example.edu.cn/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def absolute_url(value: str, base: str) -> str:
    parsed = urllib.parse.urlsplit(urllib.parse.urljoin(base, value))
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def root_domain(host: str) -> str:
    parts = host.lower().split(".")
    return ".".join(parts[-3:]) if host.endswith(".edu.cn") and len(parts) >= 3 else ".".join(parts[-2:])


def same_site(url: str, domain: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    return host == domain or host.endswith(f".{domain}")


def path_ext(url: str) -> str:
    return Path(urllib.parse.urlsplit(url).path.lower()).suffix


def fetch(url: str, timeout: int = 20) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get_content_type()


def decode_html(content: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    return content.decode("utf-8", errors="replace")


def robots_allowed(url: str, cache: dict[str, urllib.robotparser.RobotFileParser]) -> bool:
    parsed = urllib.parse.urlsplit(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        parser = urllib.robotparser.RobotFileParser(f"{origin}/robots.txt")
        try:
            parser.read()
        except Exception:
            return True
        cache[origin] = parser
    return cache[origin].can_fetch(USER_AGENT, url)


def extract_date(text: str) -> str:
    match = DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def score_text(mode: str, url: str, text: str) -> tuple[int, str]:
    haystack = f"{urllib.parse.unquote(url)} {text}".lower()
    matched = [keyword for keyword in COLLECTOR_KEYWORDS[mode] if keyword.lower() in haystack]
    score = len(matched) * 5
    ext = path_ext(url)
    if mode == "logo":
        if "logo" in haystack:
            score += 8
        if ext == ".svg":
            score += 8
        elif ext in {".png", ".ico", ".zip", ".rar", ".7z"}:
            score += 5
    elif extract_date(text):
        score += 3
    reason = f"匹配关键词：{', '.join(matched[:4])}" if matched else "来自相关栏目"
    return score, reason


def should_follow(mode: str, url: str, text: str) -> bool:
    if path_ext(url) in ASSET_EXTENSIONS:
        return False
    haystack = f"{urllib.parse.unquote(url)} {text}".lower()
    return any(keyword.lower() in haystack for keyword in COLLECTOR_KEYWORDS[mode])


def collect(start_url: str, mode: str, max_pages: int = 12) -> dict[str, object]:
    if mode not in COLLECTOR_KEYWORDS:
        raise ValueError("不支持的采集类型。")
    normalized = normalize_url(start_url)
    domain = root_domain(urllib.parse.urlsplit(normalized).hostname or "")
    queue = [normalized]
    visited: list[str] = []
    queued = {normalized}
    results: dict[str, ResultItem] = {}
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    robot_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    while queue and len(visited) < max(1, min(max_pages, 30)):
        page_url = queue.pop(0)
        if not robots_allowed(page_url, robot_cache):
            skipped.append({"url": page_url, "reason": "robots.txt 不允许自动访问"})
            continue
        try:
            content, content_type = fetch(page_url)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append(f"{page_url}: {exc}")
            continue
        visited.append(page_url)
        if content_type != "text/html":
            continue

        parser = PageParser()
        parser.feed(decode_html(content))
        candidates = parser.assets if mode == "logo" else parser.links
        for raw in candidates:
            target = absolute_url(raw["href"], page_url)
            if not same_site(target, domain):
                continue
            text = compact_text(raw.get("text", "") or raw.get("title", ""))
            score, reason = score_text(mode, target, text)
            ext = path_ext(target)
            threshold = 8 if mode == "logo" else 5
            if score < threshold:
                continue
            title = text or urllib.parse.unquote(Path(urllib.parse.urlsplit(target).path).name) or target
            item = ResultItem(
                title=title[:240],
                category=mode,
                url=target,
                source_page=page_url,
                date=extract_date(f"{text} {target}"),
                file_type=ext.lstrip(".").upper(),
                score=score,
                reason=reason,
                preview_url=target if mode == "logo" and ext in IMAGE_EXTENSIONS else "",
            )
            if target not in results or item.score > results[target].score:
                results[target] = item

        for link in parser.links:
            target = absolute_url(link["href"], page_url)
            text = compact_text(link.get("text", "") or link.get("title", ""))
            if (
                same_site(target, domain)
                and target not in queued
                and should_follow(mode, target, text)
            ):
                queue.append(target)
                queued.add(target)
        if queue:
            time.sleep(0.25)

    items = sorted(results.values(), key=lambda item: (item.date, item.score), reverse=True)
    return {
        "mode": mode,
        "start_url": normalized,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "visited_pages": visited,
        "errors": errors,
        "skipped": skipped,
        "items": [item.to_dict() for item in items],
    }


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return cleaned or "campus-file"


def download_file(url: str, output_dir: Path) -> Path:
    normalized = normalize_url(url)
    content, content_type = fetch(normalized, timeout=60)
    filename = urllib.parse.unquote(Path(urllib.parse.urlsplit(normalized).path).name) or "campus-file"
    if not Path(filename).suffix:
        filename += mimetypes.guess_extension(content_type) or ".bin"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / safe_filename(filename)
    counter = 2
    while path.exists():
        path = output_dir / f"{path.stem}-{counter}{path.suffix}"
        counter += 1
    path.write_bytes(content)
    return path


def export_results(items: list[dict[str, object]], export_format: str) -> tuple[bytes, str, str]:
    fields = [
        "school", "province", "query_year", "year", "material_label", "title", "category",
        "date", "source_authority", "department", "url", "source_page",
        "file_type", "score", "reason",
    ]
    if export_format == "json":
        return json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", "json"
    if export_format == "md":
        lines = ["# CampusCrawler 采集结果", ""]
        for item in items:
            lines.extend([
                f"## {item.get('title', '未命名')}",
                f"- 学校：{item.get('school', '')}",
                f"- 省份：{item.get('province', '')}",
                f"- 年份：{item.get('year', '')}",
                f"- 资料类型：{item.get('material_label', '')}",
                f"- 类型：{item.get('category', '')}",
                f"- 日期：{item.get('date', '')}",
                f"- 来源机构：{item.get('source_authority', '')}",
                f"- 链接：{item.get('url', '')}",
                f"- 来源：{item.get('source_page', '')}",
                "",
            ])
        return "\n".join(lines).encode("utf-8"), "text/markdown", "md"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(items)
    return ("\ufeff" + output.getvalue()).encode("utf-8"), "text/csv", "csv"
