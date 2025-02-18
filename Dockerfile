FROM centos:7
MAINTAINER tecnologia@scielo.org

# Actualizar repositorios y instalar dependencias
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* && \
    yum clean all && \
    yum makecache && \
    yum -y install gcc epel-release python-devel python-pip && \
    yum -y upgrade python-setuptools

# Copiar y configurar la aplicación
COPY . /app
RUN pip install -r /app/requirements.txt && \
    chmod -R 755 /app/* && \
    python setup.py install

WORKDIR /app