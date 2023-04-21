#!/bin/bash
# Check if ovpn.env.dev file exists
if [ -e ./services/openvpn/ovpn.env.dev ] || [ -e ovpn.env.dev ]; then
    source ovpn.env.dev
else
    echo "Please set up your ovpn.env file before starting your environment."
    exit 1
fi

docker-compose run --rm openvpn ovpn_genconfig -u $PROTO://$HOSTNAME
docker-compose run --rm openvpn ovpn_initpki