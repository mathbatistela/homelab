FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Read routes only. Spec creation (POST /specs) belongs on 8791, which the
# compose file publishes on 127.0.0.1, and needs a SECOND ASGI app or a second
# process with its own CMD: adding the route to tiao_web.app:app would publish
# the write path on 8790 too, i.e. through Pangolin behind only the PIN.
EXPOSE 8790
CMD ["uvicorn", "tiao_web.app:app", "--host", "0.0.0.0", "--port", "8790"]
