FROM centos:7
MAINTAINER tecnologia@scielo.org

# Atualizar repositórios e instalar dependências
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-* && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-* && \
    yum clean all && \
    yum makecache && \
    yum -y install gcc epel-release python-devel curl

# Instalar pip usando get-pip.py
RUN curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py && \
    python get-pip.py && \
    rm get-pip.py

# Copiar e configurar a aplicação
COPY . /app
WORKDIR /app

# Instalar requisitos e configurar a aplicação
RUN pip install -r requirements.txt && \
    chmod -R 755 /app/* && \
    python setup.py install