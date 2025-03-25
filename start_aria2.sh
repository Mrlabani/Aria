#!/bin/bash
tracker_list=$(curl -Ns https://ngosang.github.io/trackerslist/trackers_all_http.txt | awk '$0' | tr '\n\n' ',')
aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all \
       --bt-tracker="[$tracker_list]" --max-connection-per-server=10 --split=10 \
       --max-concurrent-downloads=5 --seed-ratio=0 --daemon=true
       