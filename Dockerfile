FROM python:3.10-slim

# Install dependencies
RUN mkdir /app
WORKDIR /app


COPY pl_lens_app /app/pl_lens_app

ENV VIRTUAL_ENV=/usr/local
RUN python3 -m pip install pip --upgrade

COPY requirements.txt /app
COPY run.py /app
COPY gunicorn.sh /app

RUN pip install -r requirements.txt

EXPOSE 80

RUN ["chmod", "+x", "./gunicorn.sh"]

ENTRYPOINT ["./gunicorn.sh"]
