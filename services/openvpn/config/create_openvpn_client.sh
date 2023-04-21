#!/bin/bash
# $1: Clientname
# $2: nopass if needed
if [ -z $1 ] && [ -z $2 ]; then
  echo "Please provide username and passphrase as argument 1 and 2 respectively."
  exit 1
fi

docker-compose run --rm openvpn easyrsa build-client-full $1
bash ./get-client-conf.sh $1
echo $(date '+%Y %b %d %H:%M'): created $1 >> VPNclients.log