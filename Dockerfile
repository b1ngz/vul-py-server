FROM python:2.7.14

LABEL maintainer="blinking.yan@gmail.com"

RUN adduser --disabled-password --gecos '' www

RUN adduser --disabled-password --gecos '' dev

ADD code/ /home/www/code/

ADD log /home/dev/log

ADD script /home/dev/bin

RUN chown -R www:www /home/www/

RUN chown -R dev:dev /home/dev/

WORKDIR /home/www/code

CMD su -m www -c "python httpServer.py 1>log.txt 2>&1"