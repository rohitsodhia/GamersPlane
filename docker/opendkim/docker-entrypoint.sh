#!/bin/sh

set -x

syslogd

CONF_FILE="/etc/opendkim/opendkim.conf"
sed -i -r -e "s/^(Domain\s+)gamersplane.com$/\1$POSTFIX_MYHOSTNAME/" $CONF_FILE
sed -i -r -e "s/^(Selector\s+)key_selector$/\1$OPENDKIM_SELECTOR/" $CONF_FILE
chmod 600 $CONF_FILE

# The key is mounted read-only at runtime; opendkim refuses keys that are
# group/world readable, so copy it into place with strict ownership.
mkdir -p /etc/opendkim/keys
cp /run/opendkim-key/key.private /etc/opendkim/keys/key.private
chown opendkim /etc/opendkim/keys/key.private
chmod 600 /etc/opendkim/keys/key.private

mkdir -p /var/run/opendkim
exec opendkim -u opendkim -f
