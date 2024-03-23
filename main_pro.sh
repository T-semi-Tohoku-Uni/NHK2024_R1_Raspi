#!/bin/bash

cd /home/keigo/NHK2024/NHK2024_R1_Raspi
. ./env/bin/activate
rm -rf logs
python src/main.py

exit 0