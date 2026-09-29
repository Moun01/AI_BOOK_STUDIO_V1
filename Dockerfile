FROM python:3.12-slim
WORKDIR /studio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY static static
COPY assets assets
COPY examples/illustration-demo.png examples/illustration-demo.png
RUN useradd -m studio && mkdir data && chown -R studio:studio /studio
USER studio
VOLUME ["/studio/data"]
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
