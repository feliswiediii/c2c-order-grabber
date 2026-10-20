# Minimal Docker image for RTT benchmarking
FROM python:3.11-slim

WORKDIR /app

# Copy benchmark script
COPY measure_rtt.py .

# Make script executable
RUN chmod +x measure_rtt.py

# Run benchmark on container start
CMD ["python3", "measure_rtt.py"]
