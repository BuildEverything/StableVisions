FROM python:3.10

WORKDIR /DiscordBot

COPY requirements.txt requirements.txt

RUN python3 -m pip install python-dotenv
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "src/run.py"]
