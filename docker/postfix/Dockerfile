FROM alpine:3.24

RUN apk add --no-cache --update postfix

COPY main.cf /etc/postfix/main.cf

COPY docker-entrypoint.sh /

CMD ["/docker-entrypoint.sh"]
