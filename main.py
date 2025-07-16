from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

app = FastAPI(title="Video Scraper Tool")
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
    likes: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None

# ---------------------------------------
# OK.ru Scraper
# ---------------------------------------
def convert_to_ddmmyyyy(date_str: str) -> str:
    month_map = {
        'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04', 'май': '05', 'мая': '05',
        'июн': '06', 'июл': '07', 'авг': '08', 'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
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
            'User-Agent': 'Mozilla/5.0'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        video_details = VideoDetails(video_url=url)

        video_details.title = soup.find("meta", property="og:title")['content'] if soup.find("meta", property="og:title") else "N/A"

        duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html)
        video_details.duration = duration_match.group(1) if duration_match else "N/A"

        date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>', html)
        if date_match:
            video_details.upload_date = convert_to_ddmmyyyy(date_match.group(1).strip())

        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html)
        video_details.views = views_match.group(1).strip() if views_match else "N/A"

        channel_name_match = re.search(r'name="([^"]+)" id="[\d]+"', html)
        video_details.channel_name = channel_name_match.group(1) if channel_name_match else "N/A"

        subs_match = re.search(r'subscriberscount="(\d+)"', html)
        video_details.subscriber_count = subs_match.group(1) if subs_match else "N/A"

        # Profile URL logic
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
            match = re.search(r'"authorLink":"(\\/profile\\/[^"]+)"', html)
            if match:
                profile_url = "https://ok.ru" + match.group(1).replace("\\/", "/")

        video_details.profile_url = profile_url or "N/A"

        return video_details

    except Exception as e:
        print(f"[OK.RU ERROR] {url}: {e}")
        return VideoDetails(video_url=url, title="N/A", duration="N/A", upload_date="N/A", views="N/A",
                            profile_url="N/A", channel_name="N/A", subscriber_count="N/A")

# ---------------------------------------
# Dailymotion Scraper
# ---------------------------------------
def scrape_dailymotion_video(url: str) -> VideoDetails:
    try:
        video_id = url.split("/")[-1].split("?")[0]
        base_api = f"https://api.dailymotion.com/video/{video_id}?fields=id,title,duration,description,created_time,views_total,likes_total,owner,tags"
        video_response = requests.get(base_api, timeout=10).json()

        owner_id = video_response.get("owner")
        owner_api = f"https://api.dailymotion.com/user/{owner_id}?fields=username,followers_total"
        owner_response = requests.get(owner_api, timeout=10).json()

        return VideoDetails(
            video_url=url,
            title=video_response.get("title", "N/A"),
            duration=str(video_response.get("duration", "N/A")),
            upload_date=datetime.fromtimestamp(video_response.get("created_time", 0)).strftime("%d-%m-%Y"),
            views=str(video_response.get("views_total", "N/A")),
            likes=str(video_response.get("likes_total", "N/A")),
            description=video_response.get("description", "N/A"),
            tags=", ".join(video_response.get("tags", [])),
            channel_name=owner_response.get("username", "N/A"),
            subscriber_count=str(owner_response.get("followers_total", "N/A")),
            profile_url=f"https://www.dailymotion.com/{owner_response.get('username', '')}"
        )

    except Exception as e:
        print(f"[Dailymotion ERROR] {url}: {e}")
        return VideoDetails(video_url=url, title="N/A", duration="N/A", upload_date="N/A", views="N/A",
                            profile_url="N/A", channel_name="N/A", subscriber_count="N/A")

# ---------------------------------------
# Routes
# ---------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scrape")
async def api_scrape_video(url: str):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed_url = urlparse(url)

    if 'ok.ru' in parsed_url.netloc:
        return scrape_okru_video(url)
    elif 'dailymotion.com' in parsed_url.netloc:
        return scrape_dailymotion_video(url)
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform. Only OK.ru and Dailymotion are supported.")

# ✅ For local/Render run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
