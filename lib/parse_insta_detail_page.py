#!/usr/bin/env python
# coding: utf-8

import os
import re
import sys
import glob
from bs4 import BeautifulSoup
import simplejson as json
import MySQLdb
import argparse
from dateutil.parser import parse

import requests
import yaml

config = yaml.load(open("./config.yaml"))

GET_HTML_URL = config["API"]["GET_HTML_URL"]
HOSTNAME = config["mysql"]["host"]
USERNAME = config["mysql"]["username"]
PASSWD = config["mysql"]["passwd"]
DB_NAME = config["mysql"]["db_name"]


def get_cmd():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfiles", help="which tag to crawl")
    args = parser.parse_args()
    return args


def create_connection():
    try:
        conn = MySQLdb.connect(host=HOSTNAME, user=USERNAME, passwd=PASSWD , db=DB_NAME)
        conn.set_character_set('utf8mb4')
        return conn
    except:
        print("mysql connection error")
        exit()


def parse_one_page(html_doc):
    res = {}

    soup = BeautifulSoup(html_doc)

    try:
        like_comments = soup.find("meta", {"name": "description"})["content"].split("-")[0].strip()
        tmp_like_comments = like_comments.split(u'次赞、')
        res['likes'] = tmp_like_comments[0].strip()
        res['comments'] = tmp_like_comments[-1].split(u'条评论')[0].strip()
    except:
        res['likes'] = '0'
        res['comments'] = '0'

    try:
        username = soup.find("a", class_="FPmhX notranslate nJAzx").get_text()
        res['username'] = username
    except:
        res['username'] = ''

    try:
        location = soup.find("a", class_="O4GlU")
        res['location_name'] = location.get_text()
        res['location_url'] = location["href"]
        print(res['location_name'], res['location_url'])
        '''
        res['location_name'] = ""
        res['location_url'] = ""
        for location in soup.find_all("a", href=lambda x: x and '/explore/locations/' in x):
            if re.match(r"/explore/locations/[0-9]+/.*/", location["href"]):
                res['location_name'] = location.get_text()
                res['location_url'] = location["href"]
                break
        '''
    except:
        res['location_name'] = ""
        res['location_url'] = ""

    try:
        publish_time = soup.find("time", class_="_1o9PC Nzb55")["datetime"]
        publish_time = parse(publish_time).strftime('%Y-%m-%d %H:%M:%S')
        res['publish_time'] = publish_time
    except:
        res['publish_time'] = ''

    return res


def insert_data_into_mysql(conn, data):
    cur = conn.cursor()

    try:
        cur.execute('''INSERT INTO images (id, tag, image_url, source_page, texts, htmlID, publish_time, blogger, likes, src_site, object_detction, location_name, location_url, comments) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', (data['img_url_md5'], data['tag'], data['img_src'], data['detail_link'], data['alt'], data['detail_link_md5'], data['publish_time'], data['username'], data['likes'], data['src_site'], json.dumps(data['detect_person_res']), data['location_name'], data['location_url'], data['comments']))
#        conn.commit()
    except:
        print "insert fai"
        conn.rollback()


def main():
    paras = get_cmd()
 
    conn = create_connection()

    for inputfile in glob.glob(paras.inputfiles):
        outputfile = inputfile + '_parsed'

        finished_list = set()
        if not os.path.isfile(outputfile):
            pass
        else:
            for line in open(outputfile):
                try:
                    data = json.loads(line.strip())
                except:
                    print outputfile
                    exit()
                if 'detail_link_md5' in data.keys() and data['detail_link_md5'] not in finished_list:
                    finished_list.add(data['detail_link_md5'])

        output = open(outputfile, 'a')
        tag = inputfile.split('/')[-1].split('.')[0].strip()
        cnt = 0
        location_num = 0
        for line in open(inputfile):
            cnt += 1
            print cnt
            data = json.loads(line.strip())

            if 'detail_link_md5' in data.keys() and 'detect_person_res' in data.keys() and data['detect_person_res']['T_F'] == True:
                if data['detail_link_md5'] in finished_list:
                    print data['detail_link_md5']
                    continue
                else:
                    finished_list.add(data['detail_link_md5'])

                #html_doc = open('./data_detailpage_html/' + data['detail_link_md5']) 
                r = requests.post(GET_HTML_URL, json={'html_url_md5': data['detail_link_md5']})
                html_doc = r.json()
                #print html_doc['html']
                parse_res = parse_one_page(html_doc['html']['html'])
                for k, v in parse_res.items():
                    data[k] = v
                if data["location_name"] != '':
                    location_num += 1
                data['src_site'] = 'instagram'
                data['tag'] = tag
                insert_data_into_mysql(conn, data)
            output.write(json.dumps(data).encode('utf-8') + '\n')
        conn.commit()
        print(location_num, cnt)


if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding("utf-8")
    main()
