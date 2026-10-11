FROM alpine:3.24

RUN apk add --no-cache --upgrade opendkim inetutils-syslogd

COPY opendkim.conf /etc/opendkim/opendkim.conf

COPY docker-entrypoint.sh /

CMD ["/docker-entrypoint.sh"]
