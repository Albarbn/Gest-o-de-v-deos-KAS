from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from forex_python.converter import CurrencyRates
import yt_dlp
import requests
import isodate
import os

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

@app.route("/video-info", methods=["POST"])
def video_info():
    data = request.json
    youtube_link = data.get("youtube_link")

    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "cookiefile": "cookies.txt"  # Adiciona cookies para autenticação
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_link, download=False)
            formats = info_dict.get('formats', [])
            thumbnail = info_dict.get('thumbnail', '')
            title = info_dict.get('title', 'Título Desconhecido')

            quality_set = {}
            for f in formats:
                resolution = f.get('height', 'audio')  # 'audio' para streams só de áudio
                if resolution not in quality_set or (f.get('vcodec') != 'none' and f.get('acodec') != 'none'):
                    quality_set[resolution] = {
                        "format_id": f['format_id'],
                        "resolution": f.get('resolution', 'Somente Áudio'),
                        "format_note": f.get('format_note', ''),
                        "has_video": f.get('vcodec') != 'none',
                        "has_audio": f.get('acodec') != 'none'
                    }

            qualities = list(quality_set.values())

            return jsonify({
                "success": True,
                "title": title,
                "thumbnail": thumbnail,
                "qualities": qualities
            })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/download", methods=["POST"])
def download_video():
    data = request.json
    youtube_link = data.get("youtube_link")
    format_id = data.get("quality")

    try:
        download_folder = "downloads"
        os.makedirs(download_folder, exist_ok=True)

        ydl_opts = {
            "format": format_id,
            "outtmpl": f"{download_folder}/%(title)s.%(ext)s",  # Define nome e extensão corretamente
            "merge_output_format": "mp4"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_link, download=True)
            title = info_dict.get('title', 'Vídeo')
            file_path = os.path.join(download_folder, f"{title}.mp4")

        # Verifique se o arquivo foi gerado corretamente antes de enviá-lo
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=f"{title}.mp4")
        else:
            return jsonify({"success": False, "message": "Arquivo não encontrado após download."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    app.run(debug=True)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)