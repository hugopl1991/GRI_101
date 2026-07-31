FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Instala dependências essenciais e ferramentas para adicionar PPA
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        software-properties-common \
        build-essential \
        ca-certificates \
        wget \
        gnupg \
        python3 \
        python3-pip \
        python3-dev \
        python3-setuptools \
        pkg-config \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala GDAL e dependências geoespaciais usando o repositório padrão do Ubuntu 22.04 (GDAL 3.4.1)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        python3-gdal \
        proj-bin \
        libproj-dev \
        libgeos-dev \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Ajustes de include para compilação de bindings
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Copia requirements e projeto
COPY requirements.txt /app/requirements.txt
COPY . /app

# Garante saída de logs não bufferizada
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Atualiza pip e instala wheel; instala numpy primeiro to satisfy builds
RUN python3 -m pip install --upgrade pip wheel
RUN python3 -m pip install --no-cache-dir numpy==1.22.4

# Instala o restante das dependências (GDAL linha foi removida do requirements)
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

# Limpa arquivo de requirements para reduzir imagem
RUN rm -f /app/requirements.txt

# Executa o script por padrão; pode ser sobrescrito em docker run
#CMD ["python3", "veg_sec_weight.py"]