FROM python:3.13
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

# Install the ODBC library dependencies
RUN apt-get update && apt-get install -y \
    unixodbc-dev \
    libodbc1 \
    && rm -rf /var/lib/apt/lists/*

# Install requirements for the app
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the app into the code directory
COPY ./citi_mesh /code/citi_mesh

# Serve the app using uvicorn
CMD ["uvicorn", "citi_mesh.app:app", "--host", "0.0.0.0", "--port", "80"]