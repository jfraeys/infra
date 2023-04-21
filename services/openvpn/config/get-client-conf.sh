#!/bin/bash
mkdir -p data/client-confs
docker-compose run --rm openvpn ovpn_getclient $1 > data/client-confs/$1.ovpn