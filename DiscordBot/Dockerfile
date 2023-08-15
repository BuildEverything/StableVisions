FROM python:3.10

WORKDIR /DiscordBot

COPY requirements.txt requirements.txt

RUN python3 -m pip install python-dotenv
RUN pip3 install -r requirements.txt

RUN apt update && apt install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python3", "src/run.py"]
