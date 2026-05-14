from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
import re
import json
from bs4 import BeautifulSoup

app = FastAPI(title="Video Scraper")
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
        "янв": "01", "фев": "02", "мар": "03", "апр": "04", "май": "05", "мая": "05",
        "июн": "06", "июл": "07", "авг": "08", "сен": "09", "окт": "10", "ноя": "11", "дек": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }

    date_str = date_str.strip().replace(".", "").replace(",", "").lower()
    parts = date_str.split()

    try:
        if len(parts) >= 3:
            day = parts[0].zfill(2)
            month = month_map.get(parts[1][:3], "01")
            year = parts[2]
            return f"{day}-{month}-{year}"
    except:
        pass

    return date_str
```
date_str = date_str.strip().replace(".", "").replace(",", "").lower()
parts = date_str.split()

try:
    if "вчера" in date_str:
        return (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")
    elif len(parts) == 3:
        day = parts[0].zfill(2)
        month = month_map.get(parts[1][:3], "??")
        year = parts[2]
    elif len(parts) == 2:
        day = parts[0].zfill(2)
        month = month_map.get(parts[1][:3], "??")
        year = str(datetime.now().year)
    else:
        return date_str

    return f"{day}-{month}-{year}"

except:
    return date_str
```

def convert_iso8601_duration(iso):
match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)

```
if not match:
    return "N/A"

hours = int(match.group(1) or 0)
minutes = int(match.group(2) or 0)
seconds = int(match.group(3) or 0)

return f"{hours:02}:{minutes:02}:{seconds:02}"
```

def scrape_okru_video(url: str) -> VideoDetails:
headers = {
"User-Agent": "Mozilla/5.0"
}

```
try:
    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()

    html = res.text
    soup = BeautifulSoup(html, "html.parser")

    data = VideoDetails(video_url=url)

    data.title = (
        soup.find("meta", property="og:title")["content"].strip()
        if soup.find("meta", property="og:title")
        else "N/A"
    )

    duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html)

    if duration_match:
        duration = duration_match.group(1)
        parts = duration.split(":")

        if len(parts) == 3:
            data.duration = duration
        elif len(parts) == 2:
            data.duration = f"00:{duration}"
        else:
            data.duration = f"00:00:{duration.zfill(2)}"
    else:
        data.duration = "N/A"

    upload_match = re.search(
        r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>',
        html
    )

    data.upload_date = (
        convert_to_ddmmyyyy(upload_match.group(1))
        if upload_match else "N/A"
    )

    views_match = re.search(
        r'<div class="vp-layer-info_i"><span>(.*?)</span>',
        html
    )

    data.views = views_match.group(1).strip() if views_match else "N/A"

    channel_match = re.search(r'name="([^"]+)" id="[\d]+"', html)
    data.channel_name = channel_match.group(1) if channel_match else "N/A"

    subs_match = re.search(r'subscriberscount="(\d+)"', html)
    data.subscriber_count = subs_match.group(1) if subs_match else "N/A"

    profile_url = None
    hovercard = soup.find(attrs={"data-entity-hovercard-url": True})

    if hovercard:
        rel = hovercard["data-entity-hovercard-url"]
        profile_url = f"https://ok.ru{rel}" if rel.startswith("/") else rel

    data.profile_url = profile_url or "N/A"

    return data

except Exception as e:
    print(f"Error scraping OK.ru: {e}")

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
```

def scrape_dailymotion_video(url: str) -> VideoDetails:
try:
video_id = url.strip().split("/")[-1].split("?")[0]

```
    api = (
        f"https://api.dailymotion.com/video/{video_id}"
        f"?fields=title,duration,created_time,views_total,owner"
    )

    video_json = requests.get(api, timeout=10).json()

    owner_id = video_json.get("owner", "")

    owner_json = requests.get(
        f"https://api.dailymotion.com/user/{owner_id}?fields=username,followers_total",
        timeout=10
    ).json()

    duration_seconds = video_json.get("duration", 0)
    duration = str(timedelta(seconds=duration_seconds))

    return VideoDetails(
        video_url=url,
        title=video_json.get("title", "N/A"),
        duration=duration,
        upload_date=(
            datetime.utcfromtimestamp(
                video_json.get("created_time")
            ).strftime("%d-%m-%Y")
            if video_json.get("created_time")
            else "N/A"
        ),
        views=str(video_json.get("views_total", "N/A")),
        profile_url=f"https://www.dailymotion.com/{owner_id}",
        channel_name=owner_json.get("username", "N/A"),
        subscriber_count=str(owner_json.get("followers_total", "N/A"))
    )

except Exception as e:
    print(f"Error scraping Dailymotion: {e}")

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
```

def scrape_moj_video(url: str) -> VideoDetails:
headers = {
"User-Agent": "Mozilla/5.0"
}

```
try:
    html = requests.get(url, headers=headers, timeout=15).text

    json_matches = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        re.DOTALL
    )

    title = "N/A"
    views = "N/A"
    duration = "N/A"
    upload_date = "N/A"

    for raw_json in json_matches:
        try:
            data = json.loads(raw_json.strip())

            if data.get("@type") == "VideoObject":
                title = data.get("description") or data.get("name") or "N/A"

                upload_date = data.get("uploadDate", "N/A")

                if upload_date != "N/A":
                    upload_date = upload_date.split("T")[0]
                    dt = datetime.strptime(upload_date, "%Y-%m-%d")
                    upload_date = dt.strftime("%d-%m-%Y")

                duration = convert_iso8601_duration(data.get("duration", ""))

                interaction = data.get("interactionStatistic", [])

                for stat in interaction:
                    if (
                        stat.get("interactionType", {}).get("@type")
                        == "http://schema.org/WatchAction"
                    ):
                        views = str(
                            stat.get("userInteractionCount", "N/A")
                        )

                break

        except:
            continue

    return VideoDetails(
        video_url=url,
        title=title,
        duration=duration,
        upload_date=upload_date,
        views=views,
        profile_url="N/A",
        channel_name="Moj",
        subscriber_count="N/A"
    )

except Exception as e:
    print(f"Error scraping Moj: {e}")

    return VideoDetails(
        video_url=url,
        title="N/A",
        duration="N/A",
        upload_date="N/A",
        profile_url="N/A",
        views="N/A",
        channel_name="Moj",
        subscriber_count="N/A"
    )
```

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
return templates.TemplateResponse(
"index.html",
{"request": request}
)

@app.get("/api/scrape")
async def scrape_endpoint(url: str, platform: str = "okru"):
if not url.startswith(("http://", "https://")):
url = "https://" + url

```
parsed = urlparse(url)

if platform == "okru" and "ok.ru" in parsed.netloc:
    return scrape_okru_video(url)

elif platform == "dailymotion" and "dailymotion.com" in parsed.netloc:
    return scrape_dailymotion_video(url)

elif platform == "moj" and (
    "mojapp.in" in parsed.netloc
    or "mojvideo" in parsed.netloc
    or "share.mojapp.in" in parsed.netloc
):
    return scrape_moj_video(url)

else:
    raise HTTPException(
        status_code=400,
        detail="Unsupported platform or invalid URL."
    )
```

if **name** == "**main**":
import uvicorn

```
uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=10000
)
```
