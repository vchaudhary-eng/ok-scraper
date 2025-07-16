from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta

app = FastAPI(title="scraper-tool")
templates = Jinja2Templates(directory="templates")

class VideoDetails(BaseModel):
    video_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[str] = None
    upload_date: Optional[str] = None
    profile_url: Optional[str] = None
    views: Optional[str] = None
    channel_name: Optional[str] = None
    subscriber_count: Optional[str] = None

class IframeResult(BaseModel):
    url: str
    media_sources: List[str]

def convert_to_ddmmyyyy(date_str: str) -> str:
    month_map = {
        'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04', 'май': '05', 'мая': '05',
        'июн': '06', 'июл': '07', 'авг': '08', 'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    date_str = date_str.strip().replace('.', '').replace(',', '').lower()
    parts = date_str.split()
    try:
        if "вчера" in date_str:
            return (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")
        elif len(parts) == 3:
            day = parts[0].zfill(2)
            month = month_map.get(parts[1][:3], '??')
            year = parts[2]
        elif len(parts) == 2:
            day = parts[0].zfill(2)
            month = month_map.get(parts[1][:3], '??')
            year = str(datetime.now().year)
        elif re.match(r"\d{1,2}-\w{3,}", date_str):
            sub_parts = date_str.split('-')
            day = sub_parts[0].zfill(2)
            month = month_map.get(sub_parts[1][:3], '??')
            year = sub_parts[2] if len(sub_parts) > 2 else str(datetime.now().year)
        else:
            return date_str
        return f"{day}-{month}-{year}"
    except:
        return date_str

def scrape_okru_video(url: str) -> VideoDetails:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        html = res.text
        details = VideoDetails(video_url=url)

        title_meta = soup.find("meta", property="og:title")
        details.title = title_meta['content'].strip() if title_meta else "N/A"

        duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html)
        if duration_match:
            duration = duration_match.group(1)
            parts = duration.split(":")
            details.duration = duration if len(parts) == 3 else f"00:{duration}" if len(parts) == 2 else f"00:00:{duration.zfill(2)}"
        else:
            details.duration = "N/A"

        upload_date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>', html)
        if upload_date_match:
            details.upload_date = convert_to_ddmmyyyy(upload_date_match.group(1).strip())
        else:
            details.upload_date = "N/A"

        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html)
        details.views = views_match.group(1).strip() if views_match else "N/A"

        name_match = re.search(r'name="([^"]+)" id="[\d]+"', html)
        details.channel_name = name_match.group(1) if name_match else "N/A"

        subs_match = re.search(r'subscriberscount="(\d+)"', html)
        details.subscriber_count = subs_match.group(1) if subs_match else "N/A"

        profile_url = None
        hovercard = soup.find(attrs={"data-entity-hovercard-url": True})
        if hovercard:
            rel = hovercard.get("data-entity-hovercard-url", "")
            profile_url = "https://ok.ru" + rel if rel.startswith("/") else rel
        if not profile_url:
            og_url = soup.find("meta", property="og:url")
            if og_url:
                match = re.search(r'(https://ok\.ru/(profile|group)/[\w\d]+)', og_url.get("content", ""))
                if match:
                    profile_url = match.group(1)
        if not profile_url:
            match = re.search(r'"authorLink":"(\\/profile\\/[^\"]+)"', html)
            if match:
                profile_url = "https://ok.ru" + match.group(1).replace("\\/", "/")
        if not profile_url:
            match = re.search(r'/(group|profile)/([\w\d]+)', html)
            if match:
                profile_url = f"https://ok.ru/{match.group(1)}/{match.group(2)}"

        details.profile_url = profile_url or "N/A"
        return details

    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return VideoDetails(
            video_url=url, title="N/A", duration="N/A", upload_date="N/A",
            profile_url="N/A", views="N/A", channel_name="N/A", subscriber_count="N/A"
        )

def extract_media_sources(html: str) -> List[str]:
    sources = []
    patterns = [
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<embed[^>]+src=["\']([^"\']+)["\']',
        r'https?://[^"\']+\.m3u8',
        r'<video[^>]+src=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html, flags=re.IGNORECASE)
        for match in matches:
            if match.startswith("//"):
                sources.append("https:" + match)
            else:
                sources.append(match)
    return sources

def scrape_iframe_tool(url: str) -> IframeResult:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        html = res.text
        sources = extract_media_sources(html)
        return IframeResult(url=url, media_sources=sources)
    except Exception as e:
        print(f"[IFRAME ERROR] {url}: {e}")
        return IframeResult(url=url, media_sources=["Error fetching or parsing URL"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scrape")
async def api_scrape(url: str = Query(...), tool: str = Query("okru")):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if tool == "iframe":
        return scrape_iframe_tool(url)

    parsed_url = urlparse(url)
    if "ok.ru" not in parsed_url.netloc:
        return JSONResponse(status_code=400, content={"error": "Only ok.ru supported for OK.ru tool"})
    return scrape_okru_video(url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
