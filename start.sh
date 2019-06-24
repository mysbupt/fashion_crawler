#!/bin/bash

city_list=("Cape Town" "Hong Kong" "London" "Los Angeles" "Milan" "Moscow" "New York" "Paris" "Rio de Janeiro" "Seoul" "Shanghai" "Singapore" "Sydney" "Tokyo")
port_list=($(ps -ef | grep qTfnN | grep -v grep | awk '{print $(NF-1)}'))
port_list+=("no")

city_num=${#city_list[@]}
port_num=${#port_list[@]}

min_num=$city_num
echo "city num: $city_num port num: $port_num"
if [ $city_num -ne $port_num ]; then
    echo "the number of cities does not equal to proxy ports !!"
    min_num=$(($city_list<$port_list?$city_list:$port_list))
fi

start_cmd="gnome-terminal"
time_sleep=0
for ((i=0;i<min_num;i++)); do
    city=${city_list[$i]}
    port=${port_list[$i]}
    echo -n "start to crawl city $city: "

    # archive all the downloaded info
    cat "data/${city}.txt" >> "data/${city}.txt.backup"
    echo > "data/${city}.txt"

    tmp_cmd="--tab -e 'python crawl_by_location.py -l \"$city\" -p $port -s $time_sleep'"
    echo $tmp_cmd
    start_cmd="$start_cmd $tmp_cmd"
    time_sleep=$((time_sleep+20))
done

echo $start_cmd
eval $start_cmd
