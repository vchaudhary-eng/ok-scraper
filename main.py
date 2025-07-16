from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

app = FastAPI(title="video-scraper")
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
        else:
            return date_str
        return f"{day}-{month}-{year}"
    except:
        return date_str

def scrape_okru_video(url: str) -> VideoDetails:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        video_details = VideoDetails(video_url=url)
        title_meta = soup.find("meta", property="og:title")
        video_details.title = title_meta['content'].strip() if title_meta else "N/A"
        duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html, re.IGNORECASE)
        if duration_match:
            duration_str = duration_match.group(1)
            time_parts = duration_str.split(":")
            video_details.duration = ":".join([p.zfill(2) for p in time_parts])
        else:
            video_details.duration = "N/A"
        upload_date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>', html, re.IGNORECASE)
        if upload_date_match:
            raw_date = upload_date_match.group(1).strip()
            video_details.upload_date = convert_to_ddmmyyyy(raw_date)
        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html, re.IGNORECASE)
        video_details.views = views_match.group(1).strip() if views_match else "N/A"
        channel_name_match = re.search(r'name="([^"]+)" id="[\d]+"', html, re.IGNORECASE)
        video_details.channel_name = channel_name_match.group(1) if channel_name_match else "N/A"
        subs_match = re.search(r'subscriberscount="(\d+)"', html, re.IGNORECASE)
        video_details.subscriber_count = subs_match.group(1) if subs_match else "N/A"
        profile_url = None
        hovercard = soup.find(attrs={"data-entity-hovercard-url": True})
        if hovercard:
            rel = hovercard.get("data-entity-hovercard-url", "")
            profile_url = "https://ok.ru" + rel if rel.startswith("/") else rel
        if not profile_url:
            match = re.search(r'(https://ok\.ru/(profile|group)/[\w\d]+)', html)
            profile_url = match.group(1) if match else None
        if not profile_url:
            match = re.search(r'/(group|profile)/([\w\d]+)', html)
            profile_url = f"https://ok.ru/{match.group(1)}/{match.group(2)}" if match else None
        video_details.profile_url = profile_url or "N/A"
        return video_details
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return VideoDetails(video_url=url, title="N/A")

def scrape_vk_video(url: str) -> VideoDetails:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text
        title_match = re.search(r'<title>(.*?)</title>', html)
        title = title_match.group(1).strip() if title_match else "N/A"
        duration_match = re.search(r'<meta property="og:duration" content="(\d+)"', html)
        duration = duration_match.group(1) if duration_match else "N/A"
        stats_match = re.search(r'Views: (\d+).*?Likes: (\d+)', html)
        views = stats_match.group(1) if stats_match else "N/A"
        return VideoDetails(
            video_url=url,
            title=title,
            duration=duration,
            views=views,
            profile_url="N/A",
            channel_name="N/A",
            subscriber_count="N/A",
            upload_date="N/A"
        )
    except Exception as e:
        print("[VK ERROR]", e)
        return VideoDetails(video_url=url, title="Error")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/scrape")
async def api_scrape_video(request: Request, urls: str = Form(...), platform: str = Form(...)):
    results = []
    for url in urls.strip().splitlines():
        url = url.strip()
        if platform == "okru":
            result = scrape_okru_video(url)
        elif platform == "vk":
            result = scrape_vk_video(url)
        else:
            result = VideoDetails(video_url=url, title="Unsupported Platform")
        results.append(result)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
