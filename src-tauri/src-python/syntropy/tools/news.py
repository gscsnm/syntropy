from typing import List, Dict, Any, Callable, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import random
import re
import time
from textwrap import dedent
from urllib.parse import quote_plus

from ddgs import DDGS

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig, JsonCssExtractionStrategy

from agno.agent import Agent
from pydantic import BaseModel

from .utils import normalize_cn_symbol, throttle

logger = logging.getLogger(__name__)


def _is_rate_limited_error(err: Exception) -> bool:
    text = str(err or "").lower()
    needles = (
        "too many requests",
        "rate limit",
        "ratelimit",
        "http 429",
        "status code 429",
        "temporarily blocked",
        "throttle",
    )
    return any(x in text for x in needles)


def _sleep_retry(attempt: int) -> None:
    base = 1.0 * (2 ** attempt)
    delay = min(10.0, base) + random.uniform(0.0, 0.5)
    time.sleep(delay)


def _ddgs_news_with_retry(
    query: str,
    limit: int,
    *,
    region: str = "us-en",
    timelimit: str = "m",
):
    last_err = None
    for attempt in range(4):
        try:
            throttle("ddgs", 1.5)
            with DDGS() as ddgs:
                return list(
                    ddgs.news(
                        query=query,
                        region=region,
                        safesearch="moderate",
                        timelimit=timelimit,
                        max_results=limit,
                    )
                )
        except Exception as e:
            last_err = e
            if attempt < 3 and _is_rate_limited_error(e):
                _sleep_retry(attempt)
                continue
            raise
    if last_err is not None:
        raise last_err


async def _crawl4ai_extract_eastmoney_articles(urls: List[str]) -> Dict[str, str]:
    schema = {
        "name": "Eastmoney Article",
        "baseSelector": "body",
        "fields": [
            {
                "name": "content",
                "selector": "div#ContentBody",
                "type": "text",
            }
        ],
    }
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=False)
    run_config = CrawlerRunConfig(
        magic=True,
        remove_overlay_elements=True,
        page_timeout=60000,
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
    )

    extracted: Dict[str, str] = {}
    if not urls:
        return extracted

    async with AsyncWebCrawler() as crawler:
        tasks = [crawler.arun(url=url, config=run_config) for url in urls if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, res in zip([u for u in urls if u], results):
            if isinstance(res, Exception):
                continue
            if not getattr(res, "success", False):
                continue
            payload = getattr(res, "extracted_content", None)
            if not payload:
                continue

            data = None
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                except Exception:
                    data = None
            elif isinstance(payload, (list, dict)):
                data = payload

            items: List[dict] = []
            if isinstance(data, list):
                items = [x for x in data if isinstance(x, dict)]
            elif isinstance(data, dict):
                items = [data]

            if not items:
                continue

            contents: List[str] = []
            for item in items:
                content = item.get("content")
                if isinstance(content, str):
                    text = content.strip()
                    if text:
                        contents.append(text)

            if not contents:
                continue

            text = "\n".join(contents).strip()
            if text:
                extracted[url] = text
    return extracted


def _crawl4ai_extract_eastmoney_articles_sync(urls: List[str]) -> Dict[str, str]:
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                lambda: asyncio.run(_crawl4ai_extract_eastmoney_articles(urls))
            )
            return future.result()
    except RuntimeError:
        return asyncio.run(_crawl4ai_extract_eastmoney_articles(urls))


def get_company_news_by_akshare(symbol: str, limit: int = 10) -> str:
    """
    Get latest news for a specific company.
    
    Args:
        symbol: Stock symbol.
        limit: Number of news items. 
    """
    try:
        import akshare as ak

        stock = normalize_cn_symbol(symbol, "digits")
        df = ak.stock_news_em(symbol=stock)
        if df is None or df.empty:
            return f"No news found for {symbol}."

        records = df.head(limit).to_dict(orient="records")
        urls: List[str] = []
        meta: List[tuple[str, str, str, str]] = []
        snippets: List[str] = []
        for item in records:
            title = item.get("新闻标题") or item.get("title") or "No Title"
            link = item.get("新闻链接") or item.get("url") or ""
            link = str(link).strip() if link is not None else ""
            pub_time = item.get("发布时间") or item.get("date") or ""
            source = item.get("文章来源") or item.get("source") or ""
            snippet = item.get("新闻内容") or item.get("content") or ""
            urls.append(link)
            meta.append((title, link, pub_time, source))
            snippets.append(snippet)

        # extracted: Dict[str, str] = {}
        # try:
        #     extracted = _crawl4ai_extract_eastmoney_articles_sync(urls)
        # except Exception as e:
        #     logger.error(
        #         "crawl4ai extract eastmoney articles failed: %s", str(e), exc_info=True
        #     )

        merged: List[str] = []
        for i, (title, link, pub_time, source) in enumerate(meta):
            # content = extracted.get(link) or snippets[i]
            content = snippets[i]
            content = str(content).strip() if content is not None else ""
            merged.append(
                f"Title: {title}\nLink: {link}\nTime: {pub_time}\nSource: {source}\nSnippet:\n{content}\n"
            )

        if not merged:
            return f"No news found for {symbol}."

        return "\n---\n".join(merged[:limit])
    except Exception as e:
        msg = str(e)
        if "playwright" in msg.lower() and "executable doesn't exist" in msg.lower():
            logger.error(
                "Error fetching news: Playwright Chromium browser is not installed.",
                exc_info=True,
            )
            raise RuntimeError(
                "Error fetching news: Playwright Chromium browser is not installed."
            ) from e
        logger.error("get_company_news_by_akshare failed", exc_info=True)
        raise RuntimeError("Error fetching news") from e


def get_company_news_by_ddgs(symbol: str, limit: int = 5) -> str:
    """
    Get latest news for a specific company using DuckDuckGo.
    
    Args:
        symbol: Stock symbol.
        limit: Number of news items.
    """
    results: List[str] = []
    last_error: Optional[Exception] = None

    try:
        remaining = max(0, limit)
        if remaining:
            is_cn = symbol.strip().isdigit() and len(symbol.strip()) == 6
            query = (
                f"{symbol} 股票 新闻"
                if is_cn
                else f"{symbol} stock news"
            )
            region = "cn-zh" if is_cn else "us-en"
            ddg_news = _ddgs_news_with_retry(
                query=query, limit=remaining, region=region, timelimit="m"
            )
        else:
            ddg_news = []
        for item in ddg_news:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or item.get("link") or "").strip()
            source = str(item.get("source") or "").strip()
            date = str(item.get("date") or "").strip()
            body = str(item.get("body") or "").strip()

            if not title and not body and not url:
                continue

            if not title:
                title = "Untitled"

            lines = [f"Title: {title}"]
            if url:
                lines.append(f"Link: {url}")
            if source:
                lines.append(f"Source: {source}")
            if date:
                lines.append(f"Date: {date}")
            if body:
                lines.append(f"Snippet: {body}")
            results.append("\n".join(lines) + "\n")
    except Exception as e:
        logger.error("DDGS error when fetching company news", exc_info=True)
        last_error = e

    if not results:
        if last_error is not None:
            raise RuntimeError("Error fetching company news") from last_error
        return f"No news found for {symbol}."

    return "\n---\n".join(results[:limit])

def get_global_news(keywords: str = "financial markets economics", limit: int = 5) -> str:
    """
    Get global financial news.
    """
    try:
        results = _ddgs_news_with_retry(query=keywords, limit=limit, region="us-en", timelimit="w")
        formatted = []
        for item in results:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or item.get("link") or "").strip()
            source = str(item.get("source") or "").strip()
            date = str(item.get("date") or "").strip()
            body = str(item.get("body") or "").strip()
            if not title and not body and not url:
                continue
            if not title:
                title = "Untitled"

            lines = [f"Title: {title}"]
            if url:
                lines.append(f"Link: {url}")
            if source:
                lines.append(f"Source: {source}")
            if date:
                lines.append(f"Date: {date}")
            if body:
                lines.append(f"Snippet: {body}")
            formatted.append("\n".join(lines) + "\n")
        return "\n---\n".join(formatted)
    except Exception as e:
        logger.error("Error fetching global news", exc_info=True)
        raise RuntimeError("Error fetching global news") from e


class CleanedUrlContent(BaseModel):
    title: str = ""
    content: str = ""


def _clip_text(text: str, max_chars: int) -> str:
    value = text or ""
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    half = max(1, max_chars // 2)
    return f"{value[:half]}\n\n...[TRUNCATED]...\n\n{value[-half:]}"


async def _crawl4ai_extract_markdown(urls: List[str]) -> Dict[str, str]:
    run_config = CrawlerRunConfig(
        magic=True,
        remove_overlay_elements=True,
        page_timeout=10000,
        cache_mode=CacheMode.BYPASS,
    )

    extracted: Dict[str, str] = {}
    if not urls:
        return extracted

    async with AsyncWebCrawler() as crawler:
        tasks = [crawler.arun(url=url, config=run_config) for url in urls if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, res in zip([u for u in urls if u], results):
            if isinstance(res, Exception):
                logger.error(f"crawl4ai crawl failed: {url}", exc_info=True)
                continue
            if not getattr(res, "success", False):
                continue
            md_obj = getattr(res, "markdown", None)
            raw_md = getattr(md_obj, "raw_markdown", None) if md_obj is not None else None
            if not isinstance(raw_md, str):
                continue
            md = raw_md.strip()
            if md:
                extracted[url] = md
    return extracted


def _crawl4ai_extract_markdown_sync(urls: List[str]) -> Dict[str, str]:
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(_crawl4ai_extract_markdown(urls)))
            return future.result()
    except RuntimeError:
        return asyncio.run(_crawl4ai_extract_markdown(urls))


def _parse_cleaned_url_content(value: Any) -> CleanedUrlContent:
    if isinstance(value, CleanedUrlContent):
        return value
    if isinstance(value, dict):
        try:
            return CleanedUrlContent(**value)
        except Exception:
            return CleanedUrlContent(title=str(value.get("title") or ""), content=str(value.get("content") or ""))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return CleanedUrlContent()
        try:
            return CleanedUrlContent(**json.loads(text))
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return CleanedUrlContent(**json.loads(m.group(0)))
            except Exception:
                pass
        return CleanedUrlContent(content=text)
    return CleanedUrlContent(content=str(value))


def create_url_content_crawler(model=None) -> Callable[[List[str]], str]:
    cleaner = Agent(
        name="UrlContentCleaner",
        role="Extract main title and main content from web page markdown",
        model=model,
        add_datetime_to_context=False,
        markdown=False,
        instructions=dedent(
            """
            Input: a URL and the page markdown content.

            Task:
            - Extract the article's main title and the article's main body content from the markdown.
            - Remove boilerplate: navigation, menus, footer, copyright, cookie notices, paywall prompts,
              login/sign-up prompts, sidebars, related/recommended links, ads, trackers, social buttons,
              app download prompts, and duplicated blocks.
            - Preserve the original wording and language exactly. Do not translate. Do not summarize.
              Do not paraphrase. Do not add any new information.
            - Keep the original paragraph order. Keep headings that are part of the article body.
            - If you cannot confidently determine the title, output an empty string for title.

            Output:
            - Return ONLY valid JSON with exactly these keys: "title", "content".
            - "content" should be the cleaned main article text in markdown/plaintext form (no extra wrappers).
            """
        ).strip(),
    )

    def crawl_url_content(urls: List[str]) -> str:
        """
        Fetches page content and extracts the main title/body per URL into readable blocks.
        
        Args:
            urls: List of URL strings; order and indexes are preserved (empty strings allowed).
        
        Returns:
            A single string of result blocks separated by "\\n---\\n", where each block includes
            Index/Link/Title/Content or an error message when fetching/cleaning fails.
        """
        try:
            if not urls:
                raise RuntimeError("Error: No Url provided (urls is empty array)")


            normalized_urls: List[str] = []
            invalid_indexes: List[int] = []
            for i, u in enumerate(urls):
                s = str(u or "").strip()
                normalized_urls.append(s)
                if not s:
                    invalid_indexes.append(i)

            valid_urls = [u for u in normalized_urls if u]
            markdown_map = _crawl4ai_extract_markdown_sync(valid_urls) if valid_urls else {}

            blocks: List[str] = []
            for i, target in enumerate(normalized_urls):
                if not target:
                    blocks.append(f"Index: {i}\nError: 提供的Url是空的\n")
                    continue

                markdown = (markdown_map.get(target) or "").strip()
                if not markdown:
                    blocks.append(
                        "\n".join(
                            [
                                f"Index: {i}",
                                f"Link: {target}",
                                "Error: crawl4ai failed to fetch markdown content (may be blocked/timeout/no body)",
                                "",
                            ]
                        )
                    )
                    continue

                clipped = _clip_text(markdown, 50000)
                try:
                    run_output = cleaner.run(
                        input=f"URL: {target}\n\nMARKDOWN:\n{clipped}",
                        output_schema=CleanedUrlContent,
                    )
                    cleaned = _parse_cleaned_url_content(getattr(run_output, "content", None))
                except Exception as e:
                    blocks.append(
                        "\n".join(
                            [
                                f"Index: {i}",
                                f"Link: {target}",
                                f"Error: Content cleaning failed: {e}",
                                "",
                            ]
                        )
                    )
                    continue
                title = (cleaned.title or "").strip()
                content = (cleaned.content or "").strip()

                if not title and not content:
                    blocks.append(
                        "\n".join(
                            [
                                f"Index: {i}",
                                f"Link: {target}",
                                "Error: The content cleaning result is empty (the model did not return a parsed title/body)",
                                "",
                            ]
                        )
                    )
                    continue

                blocks.append(
                    "\n".join(
                        [
                            f"Index: {i}",
                            f"Link: {target}",
                            f"Title: {title}" if title else "Title: (未识别到标题)",
                            "Content:",
                            content if content else "(未识别到正文内容)",
                            "",
                        ]
                    )
                )

            return "\n---\n".join([b.rstrip() for b in blocks if b is not None]).rstrip()
        except Exception as e:
            logger.error("crawl_url_content failed", exc_info=True)
            raise RuntimeError("Error: crawl_url_content 执行失败") from e

    crawl_url_content.__name__ = "crawl_url_content"
    return crawl_url_content


async def _crawl4ai_baidu_news_search(keyword: str, limit: int = 10) -> List[Dict[str, str]]:
    kw = str(keyword or "").strip()
    if not kw:
        return []

    url = f"https://www.baidu.com/s?tn=news&rtt=1&bsst=1&wd={quote_plus(kw)}"
    schema = {
        "name": "Baidu News Search Results",
        "baseSelector": "div.result-op, div[class*='result-op'], div.c-result, div[class*='c-result']",
        "fields": [
            {
                "name": "title",
                "selector": "h3[class*='news-title'] a",
                "type": "text",
            },
            {
                "name": "link",
                "selector": "h3[class*='news-title'] a",
                "type": "attribute",
                "attribute": "href",
            },
            {
                "name": "time",
                "selector": "div[class*='content-wrapper'] span.c-color-gray2, div[class*='content-wrapper'] span[aria-label^='发布于']",
                "type": "text",
            },
            {
                "name": "snippet",
                "selector": "div[class*='content-wrapper'] span.c-font-normal.c-color-text",
                "type": "text",
            },
            {
                "name": "source",
                "selector": "div[class*='news-source'] span.c-color-gray, span[aria-label^='新闻来源']",
                "type": "text",
            },
        ],
    }
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=False)
    run_config = CrawlerRunConfig(
        magic=True,
        remove_overlay_elements=True,
        page_timeout=30000,
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
    )

    async with AsyncWebCrawler() as crawler:
        res = await crawler.arun(url=url, config=run_config)
        if not getattr(res, "success", False):
            return []
        payload = getattr(res, "extracted_content", None)
        if not payload:
            return []

        data: Any = None
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except Exception:
                data = None
        elif isinstance(payload, (list, dict)):
            data = payload

        items: List[dict] = []
        if isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]
        elif isinstance(data, dict):
            items = [data]

        results: List[Dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            t = str(item.get("time") or "").strip()
            source = str(item.get("source") or "").strip()
            snippet = str(item.get("snippet") or "").strip()

            if not title and not link and not snippet:
                continue

            key = link or title or snippet
            if key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "title": title,
                    "link": link,
                    "time": t,
                    "source": source,
                    "snippet": snippet,
                }
            )
            if limit > 0 and len(results) >= limit:
                break

        return results


def _crawl4ai_baidu_news_search_sync(keyword: str, limit: int = 10) -> List[Dict[str, str]]:
    try:
        asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                lambda: asyncio.run(_crawl4ai_baidu_news_search(keyword, limit))
            )
            return future.result()
    except RuntimeError:
        return asyncio.run(_crawl4ai_baidu_news_search(keyword, limit))


def search_baidu_news(keyword: str) -> str:
    """
    Search Baidu News results by keyword using Crawl4AI (LLM-free JSON extraction).

    Args:
        keyword: The search keyword used to build the Baidu News query URL.

    Returns:
        A human-readable string containing multiple result blocks separated by '---'.
        Each block includes Title/Link/Time/Source/Snippet when available.
        If keyword is empty or an error occurs, returns an error message string.
    """
    limit = 10
    kw = str(keyword or "").strip()
    if not kw:
        raise RuntimeError("Error: The keyword is empty")

    try:
        items = _crawl4ai_baidu_news_search_sync(kw, limit)
        if not items:
            return f"No news found for keywords: {kw}"

        blocks: List[str] = []
        for it in items[: max(0, int(limit) or 0) if limit else len(items)]:
            title = str(it.get("title") or "").strip() or "Untitled"
            link = str(it.get("link") or "").strip()
            t = str(it.get("time") or "").strip()
            source = str(it.get("source") or "").strip()
            snippet = str(it.get("snippet") or "").strip()

            lines: List[str] = [f"Title: {title}"]
            if link:
                lines.append(f"Link: {link}")
            if t:
                lines.append(f"Time: {t}")
            if source:
                lines.append(f"Source: {source}")
            if snippet:
                lines.append(f"Snippet: {snippet}")
            blocks.append("\n".join(lines) + "\n")
        return "\n---\n".join(blocks)
    except Exception as e:
        logger.error("baidu news search failed", exc_info=True)
        raise RuntimeError("Error searching baidu news") from e
