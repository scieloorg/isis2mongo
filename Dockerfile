FROM centos:7
MAINTAINER tecnologia@scielo.org

# Actualizar repositorios y instalar dependencias
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* && \
    yum clean all && \
    yum makecache && \
    yum -y install gcc epel-release python-devel

# Instalar pip usando easy_install
RUN yum -y install python-setuptools && \
    easy_install pip

# Copiar y configurar la aplicación
COPY . /app
WORKDIR /app

# Instalar requisitos y configurar la aplicación
RUN pip install -r requirements.txt && \
    chmod -R 755 /app/* && \
    python setup.py install