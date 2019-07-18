#!/usr/bin/env python
# coding: utf-8

import os
import re
import sys
from bs4 import BeautifulSoup
import argparse

import datetime
import requests
import yaml


def parse_num(ori_str):
    num = None
    if "," in ori_str:
        ori_str = ori_str.replace(",", "")
    if "K" in ori_str:
        num = int(float(ori_str.split("K")[0]) * 1000)
    if "M" in ori_str:
        num = int(float(ori_str.split("M")[0]) * 1000000)
    if num is None:
        num = int(ori_str)

    return num


def parse_user_page(html_doc):
    res = {}

    soup = BeautifulSoup(html_doc, "lxml")

    try:
        user_type = soup.find("script", {"type": "application/ld+json"}).text.strip()
    except:
        user_type = "fail"

    try:
        desc = soup.find("meta", {"name": "description"})["content"]
    except:
        desc = "fail"

    fans = -1
    follows = -1
    posts = -1
    if desc != "fail":
        x = desc.split(" - ")[0]
        fans, follows, posts = x.split(u"、")
        fans = fans.split(u"位粉丝")[0].strip()
        fans = parse_num(fans)

        follows = follows.split(u"已关注")[1].strip().split(u"人")[0].strip()
        follows = parse_num(follows)

        posts = posts.split(u"篇帖子")[0].strip()
        posts = parse_num(posts)

    res = {
        "desc": desc,
        "fans": fans,
        "follows": follows,
        "posts": posts,
        "user_type": user_type
    }

    return res 
