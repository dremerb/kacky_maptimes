FROM python

WORKDIR /opt/kack

COPY . /opt/kack

pip3 install -r requirements.txt

EXPOSE 5000

ENV FLASK_APP=app
CMD ["flask run"]