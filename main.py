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

app = FastAPI(title="okru-scraper")
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
        elif re.match(r"\d{1,2}-\w{3,}", date_str):  # like 15-jul-2025
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        video_details = VideoDetails(video_url=url)

        # ✅ Title
        title_meta = soup.find("meta", property="og:title")
        video_details.title = title_meta['content'].strip() if title_meta else "N/A"

        # ✅ Duration
        duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html, re.IGNORECASE)
        if duration_match:
            duration_str = duration_match.group(1)
            time_parts = duration_str.split(":")
            if len(time_parts) == 3:
                video_details.duration = duration_str
            elif len(time_parts) == 2:
                video_details.duration = f"00:{duration_str}"
            else:
                video_details.duration = f"00:00:{duration_str.zfill(2)}"
        else:
            video_details.duration = "N/A"

        # ✅ Upload date
        upload_date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>', html, re.IGNORECASE)
        if upload_date_match:
            raw_date = upload_date_match.group(1).strip()
            video_details.upload_date = convert_to_ddmmyyyy(raw_date)
        else:
            video_details.upload_date = "N/A"

        # ✅ Views
        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html, re.IGNORECASE)
        video_details.views = views_match.group(1).strip() if views_match else "N/A"

        # ✅ Channel Name
        channel_name_match = re.search(r'name="([^"]+)" id="[\d]+"', html, re.IGNORECASE)
        video_details.channel_name = channel_name_match.group(1) if channel_name_match else "N/A"

        # ✅ Subscribers
        subs_match = re.search(r'subscriberscount="(\d+)"', html, re.IGNORECASE)
        video_details.subscriber_count = subs_match.group(1) if subs_match else "N/A"

        # ✅ Profile URL
        profile_url = None

        # Method 1: Hovercard
        hovercard = soup.find(attrs={"data-entity-hovercard-url": True})
        if hovercard:
            rel = hovercard.get("data-entity-hovercard-url", "")
            if rel.startswith("/"):
                profile_url = "https://ok.ru" + rel
            else:
                profile_url = rel

        # Method 2: og:url fallback
        if not profile_url:
            og_url = soup.find("meta", property="og:url")
            if og_url:
                og_content = og_url.get("content", "")
                match = re.search(r'(https://ok\.ru/(profile|group)/[\w\d]+)', og_content)
                if match:
                    profile_url = match.group(1)

        # Method 3: JSON/script
        if not profile_url:
            match = re.search(r'"authorLink":"(\\/profile\\/[^"]+)"', html)
            if match:
                profile_url = "https://ok.ru" + match.group(1).replace("\\/", "/")

        # Method 4: Final fallback
        if not profile_url:
            match = re.search(r'/(group|profile)/([\w\d]+)', html)
            if match:
                profile_url = f"https://ok.ru/{match.group(1)}/{match.group(2)}"

        video_details.profile_url = profile_url or "N/A"

        return video_details

    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return VideoDetails(
            video_url=url,
            title="N/A",
            duration="N/A",
            upload_date="N/A",
            profile_url="N/A",
            views="N/A",
            channel_name="N/A",
            subscriber_count="N/A"
        )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scrape")
async def api_scrape_video(url: str):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed_url = urlparse(url)
    if 'ok.ru' not in parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Please provide a valid ok.ru video URL")

    return scrape_okru_video(url)

# ✅ For Render deployment
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
