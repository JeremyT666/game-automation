# Stage 1: Build layer
FROM python:3.10-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final image
FROM python:3.10-slim-bookworm
WORKDIR /app
COPY . /app

# 把 builder 的 pip 安裝路徑複製過來
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

ENTRYPOINT ["python", "-m", "pytest"]