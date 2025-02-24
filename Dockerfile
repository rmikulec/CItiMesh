FROM python:3.13
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./citi_mesh /code/citi_mesh

CMD ["uvicorn", "citi_mesh.app:app", "--host", "0.0.0.0", "--port", "80"]