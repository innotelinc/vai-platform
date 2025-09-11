# Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Force reinstall of pipecat on every build (cache bust)
ARG CACHEBUST=1
RUN pip install 'git+https://github.com/dograh-hq/pipecat.git@main#egg=pipecat-ai[cartesia,deepgram,openai,elevenlabs,groq,google,azure]'

COPY . ./api

ENV PYTHONPATH=/app

# Expose the port FastAPI will run on
EXPOSE 8000

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]