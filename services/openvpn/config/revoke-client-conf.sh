#!/bin/bash
if [ -z $1 ]; then
  echo "Please provide username as argument 1"
  exit 1
fi

docker-compose run --rm openvpn ovpn_revokeclient $1 remove
rm -f client-confs/$1.ovpn
echo $(date '+%Y %b %d %H:%M'): revoked $1 >> VPNclients.log