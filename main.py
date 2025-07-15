from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import re

app = FastAPI()
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

def scrape_okru_video(url: str) -> VideoDetails:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        html = res.text
        soup = BeautifulSoup(html, 'html.parser')

        details = VideoDetails(video_url=url)

        # ✅ Title (meta og:title)
        title_tag = soup.find("meta", property="og:title")
        details.title = title_tag["content"].strip() if title_tag and title_tag.get("content") else "N/A"

        # ✅ Duration
        dur_match = re.search(r'class="vid-card_duration">([\d:]+)<', html)
        details.duration = dur_match.group(1) if dur_match else "N/A"

        # ✅ Upload Date
        date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)<', html)
        if date_match:
            date_text = date_match.group(1).strip().lower()
            if "вчера" in date_text:
                yesterday = datetime.now() - timedelta(days=1)
                time_part = date_text.split(" ")[-1] if " " in date_text else "00:00"
                details.upload_date = f"{yesterday.strftime('%d/%m/%Y')} {time_part}"
            else:
                parts = date_text.split()
                date_part = parts[0]
                time_part = parts[1] if len(parts) > 1 else ""
                date_parts = date_part.split("-")
                if len(date_parts) >= 2:
                    day = date_parts[0]
                    month = date_parts[1]
                    year = str(datetime.now().year)
                    details.upload_date = f"{day}/{month}/{year} {time_part}".strip()
                else:
                    details.upload_date = date_text
        else:
            details.upload_date = "N/A"

        # ✅ Views
        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html)
        details.views = views_match.group(1).strip() if views_match else "N/A"

        # ✅ Channel URL
        profile_match = re.search(r'/(group|profile)/([\w\d]+)', html)
        details.profile_url = f"https://ok.ru/{profile_match.group(1)}/{profile_match.group(2)}" if profile_match else "N/A"

        # ✅ Channel Name
        name_match = re.search(r'name="([^"]+)" id="[\d]+"', html)
        details.channel_name = name_match.group(1) if name_match else "N/A"

        # ✅ Subscribers
        sub_match = re.search(r'subscriberscount="(\d+)"', html)
        details.subscriber_count = sub_match.group(1) if sub_match else "N/A"

        return details
    except Exception as e:
        print(f"Scraping error for {url}: {e}")
        return VideoDetails(video_url=url, title="N/A", duration="N/A", upload_date="N/A",
                            profile_url="N/A", views="N/A", channel_name="N/A", subscriber_count="N/A")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scrape")
async def api_scrape_video(url: str):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if "ok.ru" not in parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid OK.ru URL")
    return scrape_okru_video(url)
