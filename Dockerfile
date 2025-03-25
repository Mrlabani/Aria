FROM python:3.10

WORKDIR /app
COPY . /app

# Install required packages
RUN apt-get update && apt-get install -y aria2 && \
    pip install --no-cache-dir -r requirements.txt

# Start Aria2 in background & run bot
CMD aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all --rpc-secret=${ARIA2_SECRET} & python bot.py
