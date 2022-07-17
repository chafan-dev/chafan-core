FROM bitnami/python:3.8-prod
COPY . /chafan-core
WORKDIR /chafan-core
RUN pip3 install -r requirements.txt
EXPOSE 5000
ENV PYTHONPATH /chafan-core
ENV WEB_CONCURRENCY 1
CMD python3 scripts/upgrade-db.py; uvicorn chafan_core.app.main:app --port=5000 --host=0.0.0.0 --proxy-headers
