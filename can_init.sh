#!/bin/bash

sudo ip link set can0 up type can bitrate 1000000 dbitrate 2000000 fd on
sudo ifconfig can0 txqueuelen 1000
sudo ip link set can0 up

exit 0