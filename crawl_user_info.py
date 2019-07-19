#!/usr/bin/env python

import os
import time
import argparse
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import urllib
import requests

import sys
sys.path.insert(0, "./lib")
from parse_userpage import parse_user_page

import yaml


def get_cmd():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--city", help="which city's users to crawl, city name")
    parser.add_argument("-p", "--proxy", help="the socks5 proxy port")
    parser.add_argument("-r", "--reverse", type=bool, default=True, help="the socks5 proxy port")
    args = parser.parse_args()
    return args


def main():
    paras = get_cmd()
    proxy = paras.proxy
    city = paras.city
    reverse = paras.reverse

    city_stat = json.load(open("./city_stat.json"))
    user_list = [] 
    for user_name, post_cnt in sorted(city_stat[city]["user_stat"].items(), key=lambda i: i[1], reverse=reverse):
        user_list.append(user_name)

    res_file = "./data_userinfo/%s_json.txt" %(city)
    finished_user = set()
    if os.path.exists(res_file):
        for line in open(res_file):
            try:
                tmp_data = json.loads(line.strip())
            except:
                continue
            finished_user.add(tmp_data["user_name"])
    output = open(res_file, "a")

    chrome_options = Options()
    chrome_options.add_argument("--proxy-server=socks5://localhost" + ":" + proxy)
    if proxy != "no":
        browse_driver = webdriver.Chrome(chrome_options=chrome_options)
    else:
        browse_driver = webdriver.Chrome()
    browse_driver.set_page_load_timeout(10)

    cnt = len(finished_user)
    for user_name in user_list:
        if user_name in finished_user:
            continue
        cnt += 1
        if cnt % 10 == 1:
            print(cnt)

        url = "https://www.instagram.com/" + user_name + "/"

        try:
            browse_driver.get(url)
        except:
            time.sleep(random.randint(3, 5))
            continue
        time.sleep(2)
        try:
            res = parse_user_page(browse_driver.page_source)
        except:
            print("bad url: %s, %s" %(city, url))
            res = {}
        res["user_name"] = user_name

        output.write(json.dumps(res).encode("utf-8") + "\n")
        time.sleep(random.randint(4, 6))


if __name__ == '__main__':
    main()
