FROM python:3.6-slim
WORKDIR /pwd

RUN pip install --no-cache-dir https://github.com/drslump/pysh/archive/master.zip

ENTRYPOINT [ "/usr/local/bin/pysh" ]
