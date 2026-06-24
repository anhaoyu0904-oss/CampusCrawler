from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone

from campus_crawler import (
    ASSET_EXTENSIONS,
    PageParser,
    absolute_url,
    compact_text,
    decode_html,
    extract_date,
    fetch,
    normalize_url,
    path_ext,
    robots_allowed,
    root_domain,
    same_site,
)


CHSI_CHARTER_SEARCH = "https://gaokao.chsi.com.cn/zsgs/zhangcheng/listVerifedZszc.do"
AH_EXAM_HOME = "https://www.ahzsks.cn/"
MATERIAL_KEYWORDS = {
    "charter": ("招生章程", "本科招生章程", "章程"),
    "plan": ("招生计划", "在皖招生", "安徽招生", "分省计划", "分专业计划", "计划查询"),
    "score": ("录取分数", "历年分数", "最低分", "最低位次", "投档线", "录取查询", "录取情况"),
    "policy": ("选科要求", "招生政策", "志愿填报", "专业组", "普通高考"),
}
FOLLOW_KEYWORDS = (
    "本科招生", "招生信息", "招生网", "招生章程", "招生计划",
    "录取分数", "历年分数", "录取查询", "安徽", "admission", "undergraduate",
)
SCHOOL_ID_RE = re.compile(r"onSchItemClick\(\$event,\s*'(\d+)'\)")
RELEVANCE_KEYWORDS = ("招生", "录取", "志愿", "计划", "章程", "分数", "位次", "投档", "选科", "专业组")
EXCLUDED_KEYWORDS = ("专升本", "研究生", "硕士", "博士", "港澳台", "华侨", "台湾", "第二学士")


def classify_material(url: str, title: str) -> tuple[str, int, str]:
    haystack = f"{urllib.parse.unquote(url)} {title}".lower()
    best_type = "policy"
    best_matches: list[str] = []
    for material_type, keywords in MATERIAL_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword.lower() in haystack]
        if len(matches) > len(best_matches):
            best_type = material_type
            best_matches = matches
    score = len(best_matches) * 6
    if best_matches and ("安徽" in haystack or "在皖" in haystack):
        score += 6
    if path_ext(url) in {".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
        score += 3
    reason = f"识别为{material_label(best_type)}"
    if best_matches:
        reason += f"；匹配：{', '.join(best_matches[:3])}"
    return best_type, score, reason


def material_label(material_type: str) -> str:
    return {
        "charter": "招生章程",
        "plan": "在皖招生计划",
        "score": "录取分数/位次",
        "policy": "招生政策",
        "official_entry": "官方查询入口",
    }.get(material_type, "招生资料")


def title_year(text: str) -> str:
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else ""


def should_follow(url: str, title: str) -> bool:
    if path_ext(url) in ASSET_EXTENSIONS:
        return False
    haystack = f"{urllib.parse.unquote(url)} {title}".lower()
    return any(keyword.lower() in haystack for keyword in FOLLOW_KEYWORDS)


def build_item(
    *,
    school_name: str,
    year: int,
    title: str,
    url: str,
    source_page: str,
    source_authority: str,
    material_type: str,
    score: int,
    reason: str,
) -> dict[str, object]:
    detected_year = title_year(f"{title} {url}")
    if detected_year == str(year):
        score += 5
        reason += f"；匹配目标年份 {year}"
    return {
        "title": title[:240],
        "category": "anhui_admission",
        "url": url,
        "source_page": source_page,
        "date": extract_date(f"{title} {url}"),
        "department": source_authority,
        "file_type": path_ext(url).lstrip(".").upper(),
        "score": score,
        "reason": reason,
        "preview_url": "",
        "school": school_name,
        "province": "安徽",
        "year": detected_year,
        "query_year": str(year),
        "material_type": material_type,
        "material_label": material_label(material_type),
        "source_authority": source_authority,
    }


def collect_school_site(
    school_name: str,
    school_url: str,
    year: int,
    max_pages: int,
) -> tuple[list[dict[str, object]], list[str], list[str], list[dict[str, str]]]:
    normalized = normalize_url(school_url)
    domain = root_domain(urllib.parse.urlsplit(normalized).hostname or "")
    queue = [normalized]
    queued = {normalized}
    visited: list[str] = []
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    items: dict[str, dict[str, object]] = {}
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
        for link in parser.links:
            target = absolute_url(link["href"], page_url)
            title = compact_text(link.get("text", "") or link.get("title", ""))
            if not title or not same_site(target, domain):
                continue
            haystack = f"{title} {urllib.parse.unquote(target)}"
            if any(keyword in haystack for keyword in EXCLUDED_KEYWORDS):
                continue
            if not any(keyword in haystack for keyword in RELEVANCE_KEYWORDS):
                continue
            material_type, score, reason = classify_material(target, title)
            target_year = title_year(f"{title} {target}")
            year_relevant = not target_year or abs(int(target_year) - year) <= 4
            if score >= 6 and year_relevant:
                item = build_item(
                    school_name=school_name,
                    year=year,
                    title=title,
                    url=target,
                    source_page=page_url,
                    source_authority=f"{school_name}官方招生网站",
                    material_type=material_type,
                    score=score,
                    reason=reason,
                )
                if target not in items or int(item["score"]) > int(items[target]["score"]):
                    items[target] = item
            if (
                target not in queued
                and year_relevant
                and should_follow(target, title)
            ):
                queue.append(target)
                queued.add(target)
        if queue:
            time.sleep(0.25)

    return list(items.values()), visited, errors, skipped


def collect_chsi_charter(school_name: str, year: int) -> tuple[list[dict[str, object]], list[str]]:
    query = urllib.parse.urlencode({"method": "index", "yxmc": school_name})
    search_url = f"{CHSI_CHARTER_SEARCH}?{query}"
    try:
        content, content_type = fetch(search_url)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return [], []
    if content_type != "text/html":
        return [], [search_url]
    html = decode_html(content)
    if school_name not in html:
        return [], [search_url]
    match = SCHOOL_ID_RE.search(html)
    detail_url = (
        f"https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-{match.group(1)}.dhtml"
        if match else search_url
    )
    item = build_item(
        school_name=school_name,
        year=year,
        title=f"{school_name}{year}年招生章程（阳光高考审核发布）",
        url=detail_url,
        source_page=search_url,
        source_authority="教育部阳光高考信息平台",
        material_type="charter",
        score=24,
        reason="阳光高考公开招生章程入口",
    )
    return [item], [search_url]


def collect_anhui_admission(
    school_name: str,
    school_url: str,
    year: int,
    max_pages: int = 12,
) -> dict[str, object]:
    school_name = compact_text(school_name)
    if len(school_name) < 2:
        raise ValueError("请输入至少两个字的院校名称。")
    if year < 2020 or year > datetime.now().year + 1:
        raise ValueError("查询年份应在 2020 年至下一年度之间。")

    items: list[dict[str, object]] = []
    visited: list[str] = []
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    if school_url.strip():
        site_items, site_visited, site_errors, site_skipped = collect_school_site(
            school_name, school_url, year, max_pages
        )
        items.extend(site_items)
        visited.extend(site_visited)
        errors.extend(site_errors)
        skipped.extend(site_skipped)

    chsi_items, chsi_visited = collect_chsi_charter(school_name, year)
    items.extend(chsi_items)
    visited.extend(chsi_visited)

    items.append(build_item(
        school_name=school_name,
        year=year,
        title="安徽省教育招生考试院官方网站",
        url=AH_EXAM_HOME,
        source_page=AH_EXAM_HOME,
        source_authority="安徽省教育招生考试院",
        material_type="official_entry",
        score=30,
        reason="安徽省招生政策、公告和官方服务入口；需要登录的数据不自动采集",
    ))

    unique = {str(item["url"]): item for item in items}
    sorted_items = sorted(
        unique.values(),
        key=lambda item: (str(item.get("year", "")) == str(year), int(item.get("score", 0))),
        reverse=True,
    )
    return {
        "mode": "anhui_admission",
        "school": school_name,
        "province": "安徽",
        "year": year,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "visited_pages": visited,
        "errors": errors,
        "skipped": skipped,
        "items": sorted_items,
        "notice": "结果用于查找和核对官方资料，不代表录取预测或填报建议。",
    }
