#!/usr/bin/env python

import os
import cv2
import time
import argparse
import random
import simplejson as json
import tempfile
import redis
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import hashlib

import urllib
import requests

import sys
sys.path.insert(0, "./lib")
from parse_insta_detail_page import parse_one_page
from align_body_face_bbox import align_body_face

import reverse_geocoder as rg

import yaml

config = yaml.load(open("./config.yaml"), Loader=yaml.FullLoader)

HTML_SAVE_URL = config["API"]["HTML_SAVE_URL"] 
IMAGE_SAVE_URL = config["API"]["IMAGE_SAVE_URL"] 

PERSON_DETECT_API = config["API"]["PERSON_DETECT_API"] 
FACE_DETECT_API = config["API"]["FACE_DETECT_API"]

r = redis.StrictRedis(host=config["redis"]["host"], port=config["redis"]["port"], db=config["redis"]["db"])


def get_cmd():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--loc_name", help="which location to crawl")
    parser.add_argument("-p", "--proxy", help="the socks5 proxy port")
    args = parser.parse_args()
    return args


def if_img_in_redis(img_url_md5):
    global r
    # return True of False
    return r.hexists("map_img_url_md5", img_url_md5)
    

def add_img_to_redis(img_url_md5, img_url):
    global r
    a = r.hset("map_img_url_md5", img_url_md5, img_url)
    if not a:
        print("add img fail")


def if_detail_html_in_redis(html_url_md5):
    global r
    return r.hexists("map_html_url_md5", html_url_md5)


def add_detail_html_to_redis(detail_url_md5, detail_url):
    global r
    a = r.hset("map_detail_url_md5", detail_url_md5, detail_url)
    if not a:
        print("add html fail")


def if_loc_in_redis(loc_url_md5):
    global r
    return r.hexists("map_loc_info", loc_url_md5)


def get_loc_info(loc_url_md5):
    global r
    return r.hget("map_loc_info", loc_url_md5)


def add_loc_info_to_redis(loc_url_md5, loc_info):
    global r
    a = r.hset("map_loc_info", loc_url_md5, loc_info)
    # if the key already exits and update successfully, will return 0. So, here return either 1 or 0 is okay.
    #if not a:
    #    print "add loc info fail"
    #    exit()


def upload_image(img_url_md5, img_data):
    files = {'image': (img_url_md5, img_data)}
    r = requests.post(IMAGE_SAVE_URL, files=files, data={'database': 'instagram_scene'})
    res = r.json()
    if res['msg'] != 'success':
        print(res)
        exit()
    else:
        #pass
        print("upload image success")


def upload_html(html_url_md5, html_data):
    data = {'html': html_data, 'html_url_md5': html_url_md5, 'database': 'instagram_scene'}
    r = requests.post(HTML_SAVE_URL, json=data)
    res = r.json()
    if res['msg'] != 'success':
        print(res)
        exit()
    else:
        #pass
        print("upload html success")


def get_all_loc_info():
    global r
    all_loc_info = r.hgetall("map_loc_info")
    results = {}
    for loc_md5, res in all_loc_info.items():
        try:
            res = json.loads(res)
        except:
            continue

        results[res["url"]] = res
                
    json.dump(results, open("./all_loc_info.json", "w"))


def main():
    paras = get_cmd()
    proxy = paras.proxy
    loc_name = paras.loc_name

    loc_info = json.load(open("./city_info.json"))
    assert loc_name in loc_info
    loc_info = loc_info[loc_name]
    url = "https://www.instagram.com" + loc_info["url"]

    # chrome for crawling image list and detail page by tagname
    chrome_options = Options()
    chrome_options.add_argument("--proxy-server=socks5://localhost" + ":" + proxy)
    if proxy != "no":
        browse_driver = webdriver.Chrome(chrome_options=chrome_options)
        detail_driver = webdriver.Chrome(chrome_options=chrome_options)
    else:
        browse_driver = webdriver.Chrome()
        detail_driver = webdriver.Chrome()
    browse_driver.set_page_load_timeout(10)
    detail_driver.set_page_load_timeout(10)

    # get image list page
    browse_driver.get(url)
    time.sleep(2)
    browse_driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    last_height = browse_driver.execute_script("return document.body.scrollHeight")

    # scroll to get the image list
    cnt_total = 0
    cnt_saved_img = 0
    cnt_saved_new_img = 0
    cnt_saved_html = 0
    cnt_saved_new_html = 0

    output = open("./data/%s.txt" %(loc_name), "a")
    while True:
        print("\n\n\n loc_name %s, cnt_total: %d, cnt_saved_img: %d, cnt_saved_new_img: %d, cnt_saved_html: %d, cnt_saved_new_html: %d" %(loc_name, cnt_total, cnt_saved_img, cnt_saved_new_img, cnt_saved_html, cnt_saved_new_html))

        browse_driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.randint(2,4))

        new_height = browse_driver.execute_script("return document.body.scrollHeight")
        # if the scroll reach the end, sroll up a little to mock the website
        if new_height == last_height:
            time.sleep(random.randint(3, 5))
            browse_driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1200);")
            continue
        else:
            retry = 0 
        last_height = new_height

        # parse the html and get all the images
        imgs = browse_driver.find_elements_by_xpath('//div/div/a/div/div/img')
        print("\n\n\n\ start a new scroll \n\n\n", len(imgs))
        for num, img in enumerate(imgs):
            #try:
            cnt_total += 1
            result = {}
            result['src_site'] = 'instagram'
            #result['tag'] = tag_name
            result['alt'] = ""
            try:
               result['alt'] = img.get_attribute('alt')
               result['img_src'] = img.get_attribute('src')
            except:
               continue 
            result['detail_link'] = img.find_element_by_xpath('./ancestor::a').get_attribute('href')
            print("original detail link is: ", result['detail_link'])

             
            m = hashlib.md5()
            m.update(result['img_src'])
            img_url_md5 = m.hexdigest()
            cnt_saved_img += 1
            if if_img_in_redis(img_url_md5) == True:
                print('image download before')
                continue
            else:
                add_img_to_redis(img_url_md5, result['img_src'])

                m = hashlib.md5()
                m.update(result['detail_link'].encode("utf-8"))
                detail_url_md5 = m.hexdigest()

                if if_detail_html_in_redis(detail_url_md5) == True:
                    print('detail page downloaded before')
                    continue
                else:
                    # here start to download and analyze the image
                    tmp_file, tmp_image = tempfile.mkstemp()
                    try:
                        urllib.urlretrieve(result['img_src'], tmp_image)
                        print("download image", img_url_md5, result['img_src'])
                    except:
                        print('download image fail', result['img_src'], result['detail_link'])
                        os.close(tmp_file)
                        os.remove(tmp_image)
                        continue

                    # here call the person detection API
                    print("call person detection API")
                    person_result = requests.post(PERSON_DETECT_API, files={'image': (img_url_md5, open(tmp_image).read())}).json()
                    result["person_result"] = person_result
                    person_boxes = []
                    if person_result["T_F"] is not True:
                        os.close(tmp_file)
                        os.remove(tmp_image)
                        continue
                    else:
                        for each in person_result['result']:
                            if each[0] == 'person' and each[1] >= 0.98:
                                tmp_bbox = list(each[2])
                                tmp_bbox.append(each[1])
                                person_boxes.append(tmp_bbox)
                        if len(person_boxes) == 0:
                            os.close(tmp_file)
                            os.remove(tmp_image)
                            continue
                        result["num_of_person"] = len(person_boxes)

                    # here call the face detection API
                    print("call face detection API")
                    face_result = requests.post(FACE_DETECT_API, files={'image': (img_url_md5, open(tmp_image).read())}).json()
                    result["face_result"] = face_result
                    face_boxes = []
                    if face_result["T_F"] is not True:
                        os.close(tmp_file)
                        os.remove(tmp_image)
                        continue
                    else:
                        for each_face in face_result['result']['boxes']:
                            if each_face[4] >= 0.98:
                                face_boxes.append(each_face)
                        if len(person_boxes) == 0:
                            os.close(tmp_file)
                            os.remove(tmp_image)
                            continue
                        result["num_of_face"] = len(face_boxes)

                    # here get the height and widht of image
                    real_img = cv2.imread(tmp_image)
                    height, width, channels = real_img.shape
                    result["height"] = height
                    result["width"] = width

                    # here to align the bounding box of face and body
                    face_body_align = align_body_face(person_boxes, face_boxes, width, height)
                    result["result"] = face_body_align
                    if face_body_align["is_face_in_body"] == False:
                        os.close(tmp_file)
                        os.remove(tmp_image)
                        continue
                    if face_body_align["body_h_percent"] < 0.3 or face_body_align["face_body_h_percent"] > 0.5:
                        os.close(tmp_file)
                        os.remove(tmp_image)
                        continue

                    # upload image to cassandra storage
                    upload_image(img_url_md5, open(tmp_image, 'rb').read())
                    cnt_saved_new_img += 1
                    os.close(tmp_file)
                    os.remove(tmp_image)

                    # here to download the detail html page
                    add_detail_html_to_redis(detail_url_md5, result['detail_link'])
                    cnt_saved_html += 1 
                    try:
                        print("download html page: ", result['detail_link'])
                        detail_driver.get(result['detail_link'])
                        page_source = detail_driver.page_source
                    except:
                        detail_driver.close()
                        time.sleep(random.randint(1,3))
                        if proxy != "no":
                            detail_driver = webdriver.Chrome(chrome_options=chrome_options)
                        else:
                            detail_driver = webdriver.Chrome()
                        detail_driver.set_page_load_timeout(10)
                        print("detail_driver error and restart")
                        continue

                    # upload the html page
                    upload_html(detail_url_md5, page_source.encode('utf-8'))
                    result['detail_link_md5'] = detail_url_md5 
                    cnt_saved_new_html += 1

                    # parse the html page
                    parse_res = parse_one_page(page_source)
                    for k, v in parse_res.items():
                        result[k] = v

                    for k, v in loc_info.items():
                        result[k] = v

            output.write(json.dumps(result).encode("utf-8") + "\n")


if __name__ == '__main__':
    main()
