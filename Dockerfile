FROM python:3.11-slim

WORKDIR /code

COPY ./code/requirements.txt /code/requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /code/requirements.txt

COPY ./code /code

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]