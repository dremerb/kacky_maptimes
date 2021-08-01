FROM python:3

WORKDIR /opt/kack

COPY . /opt/kack

RUN pip3 install -r requirements.txt

EXPOSE 5000

ENV FLASK_APP=app
ENTRYPOINT ["flask", "run", "--host", "0.0.0.0"]