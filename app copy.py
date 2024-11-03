from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from forex_python.converter import CurrencyRates
import requests
import isodate

app = Flask(__name__)
api_key = "AIzaSyCYtWYgjqvA3p1xfQTLkZoiH_4toJubWGU"
channel_id = "UCwoJ6xfG9CiGmIKb1x7d8yQ"

currency_rate = CurrencyRates()
calculation_history = []  # Lista para armazenar o histórico de cálculos

def get_new_videos():
    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.search().list(part="snippet", channelId=channel_id, maxResults=8, order="date")
    response = request.execute()
    
    new_videos = []
    for item in response["items"]:
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        thumbnail = item["snippet"]["thumbnails"]["medium"]["url"]
        publish_time = item["snippet"]["publishedAt"]

        # Obter minutagem do vídeo
        video_details = youtube.videos().list(part="contentDetails", id=video_id).execute()
        duration = video_details["items"][0]["contentDetails"]["duration"]

        # Transformar a duração de ISO 8601 para segundos
        seconds = parse_duration(duration)

        new_videos.append({
            "id": video_id,
            "title": title,
            "thumbnail": thumbnail,
            "duration_seconds": seconds,
            "publish_time": publish_time,
            "value_per_minute": 2.0  # Valor fixo por minuto
        })
    
    return new_videos

def parse_duration(duration):
    duration = isodate.parse_duration(duration)
    return int(duration.total_seconds())

def get_dollar_rate():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
        response.raise_for_status()
        data = response.json()
        return data["rates"]["BRL"]
    except (requests.exceptions.RequestException, KeyError, ValueError) as e:
        print("Erro ao obter taxa de câmbio:", e)
        return None

@app.route("/")
def index():
    videos_info = get_new_videos()
    dollar_rate = get_dollar_rate()  # Obter a taxa de câmbio do dólar para real
    return render_template("index.html", videos=videos_info, dollar_rate=dollar_rate, history=calculation_history)

@app.route("/calculate", methods=["POST"])
def calculate():
    selected_videos = request.json.get("selected_videos", [])
    add_to_history = request.json.get("add_to_history", False)
    value_per_minute = 2.0
    total_dollars = 0
    video_details = []

    for video in selected_videos:
        minutes = video["duration_seconds"] / 60
        video_value = minutes * value_per_minute
        total_dollars += video_value

        video_details.append({
            "title": video["title"],
            "duration_seconds": video["duration_seconds"],
            "value": video_value
        })

    # Converte o valor total para reais
    dollar_rate = get_dollar_rate()
    total_reais = total_dollars * dollar_rate

    # Adiciona ao histórico apenas se solicitado
    if add_to_history:
        calculation_history.append({
            "videos": video_details,
            "total_dollars": total_dollars,
            "total_reais": total_reais,
            "dollar_rate": dollar_rate
        })

    return jsonify({"total_dollars": total_dollars, "total_reais": total_reais, "history": calculation_history})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    calculation_history.clear()
    return jsonify({"message": "Histórico limpo", "history": calculation_history})
