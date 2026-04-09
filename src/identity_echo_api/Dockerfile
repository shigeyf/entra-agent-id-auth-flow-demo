FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
ENV PIP_ROOT_USER_ACTION=ignore
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./identity_echo_api/

EXPOSE 8000
CMD ["uvicorn", "identity_echo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
