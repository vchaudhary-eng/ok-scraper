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

        # ✅ Title (og:title)
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
            date_text = upload_date_match.group(1).strip()
            if "вчера" in date_text.lower():
                yesterday = datetime.now() - timedelta(days=1)
                video_details.upload_date = yesterday.strftime("%d/%m/%Y")
            else:
                parts = date_text.split(" ")
                if len(parts) >= 1:
                    date_part = parts[0]
                    date_parts = date_part.split("-")
                    if len(date_parts) >= 2:
                        day = date_parts[0].zfill(2)
                        month = date_parts[1].zfill(2)
                        year = date_parts[2] if len(date_parts) == 3 else str(datetime.now().year)
                        video_details.upload_date = f"{day}/{month}/{year}"
                    else:
                        video_details.upload_date = date_text
        else:
            video_details.upload_date = "N/A"

        # ✅ Views
        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html, re.IGNORECASE)
        video_details.views = views_match.group(1).strip() if views_match else "N/A"

        # ✅ Profile URL using hovercard (more reliable)
        hovercard = soup.find(attrs={"data-entity-hovercard-url": True})
        if hovercard:
            relative = hovercard.get("data-entity-hovercard-url", "")
            if relative.startswith("/"):
                video_details.profile_url = "https://ok.ru" + relative
            else:
                video_details.profile_url = relative
        else:
            # Fallback: regex match for /group/ or /profile/
            channel_url_match = re.search(r'/(group|profile)/([\w\d]+)', html, re.IGNORECASE)
            if channel_url_match:
                video_details.profile_url = f"https://ok.ru/{channel_url_match.group(1)}/{channel_url_match.group(2)}"
            else:
                video_details.profile_url = "N/A"

        # ✅ Channel name
        channel_name_match = re.search(r'name="([^"]+)" id="[\d]+"', html, re.IGNORECASE)
        video_details.channel_name = channel_name_match.group(1) if channel_name_match else "N/A"

        # ✅ Subscribers
        subs_match = re.search(r'subscriberscount="(\d+)"', html, re.IGNORECASE)
        video_details.subscriber_count = subs_match.group(1) if subs_match else "N/A"

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
