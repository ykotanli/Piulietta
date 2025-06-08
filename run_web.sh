#!/bin/bash
cd /home/tursu/Desktop/Proje || exit

. venv/bin/activate

exec python3 web_interface.py
