FROM python:3.13-slim-bullseye
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

# Install prerequisites for adding repositories and the driver
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    curl \
    gnupg \
 && rm -rf /var/lib/apt/lists/*

# Add the Microsoft repository key and repository list for Debian 11 (Bullseye)
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list \
    > /etc/apt/sources.list.d/mssql-release.list

# Update package lists and install the Microsoft ODBC Driver 18 along with unixODBC development files
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y \
    msodbcsql18 \
    unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# Install requirements for the app
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the app into the code directory
COPY ./citi_mesh /code/citi_mesh

# Serve the app using uvicorn
CMD ["uvicorn", "citi_mesh.app:app", "--host", "0.0.0.0", "--port", "80"]