#!/bin/bash

all_pids=`ps -ef | grep crawl_by_location.py | grep -v grep | awk '{print $2}'`

for pid in $all_pids
do
    echo "kill pid: " $pid
    pkill -9 -g $pid
done

echo "kill all remaining chromedriver processes"
ps -ef | grep chromedriver | grep -v grep | awk '{print $2}' | xargs kill -9
ps -ef | grep chromium-browse | grep -v grep | awk '{print $2}' | xargs kill -9

echo "rm all the cached file of chromium"
rm -rf /tmp/.org.chromium.Chromium.*
