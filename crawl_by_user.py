#!/usr/bin/env python
# coding: utf-8

import os
import cv2
import time
import argparse
import random
import simplejson as json
import tempfile
import redis
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import hashlib

import urllib
import requests

import sys
sys.path.insert(0, "./lib")
from parse_insta_detail_page import parse_one_page
from align_body_face_bbox import align_body_face
import datetime

import reverse_geocoder as rg

import yaml

config = yaml.load(open("./config.yaml"))

HTML_SAVE_URL = config["API"]["HTML_SAVE_URL"]
IMAGE_SAVE_URL = config["API"]["IMAGE_SAVE_URL"]

PERSON_DETECT_API = config["API"]["PERSON_DETECT_API"]
FACE_DETECT_API = config["API"]["FACE_DETECT_API"]

r = redis.StrictRedis(host=config["redis"]["host"], port=config["redis"]["port"], db=config["redis"]["db"])


def get_cmd():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", default=None, help="which file of users to crawl")
    parser.add_argument("-k", "--key", default=None, help="which key in the specific file to crawl")
    parser.add_argument("-s", "--start", default=0, type=int, help="which line to start")
    parser.add_argument("-e", "--end", default=100, type=int, help="which line to end")
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
    return r.hexists("map_detail_url_md5", html_url_md5)


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


def filter_image(img_src, img_url_md5, detail_link):
    each_result = {}
    print("go into filter image")
    # here start to download and analyze the image
    tmp_file, tmp_image = tempfile.mkstemp()
    try:
        urllib.urlretrieve(img_src, tmp_image)
        print("download image", img_url_md5, img_src)
    except:
        print('download image fail', img_src, detail_link)
        os.close(tmp_file)
        os.remove(tmp_image)
        return None

    # here call the person detection API
    print("call person detection API")
    person_result = requests.post(PERSON_DETECT_API, files={'image': (img_url_md5, open(tmp_image).read())}).json()
    each_result["person_result"] = person_result
    person_boxes = []
    if person_result["T_F"] is not True:
        os.close(tmp_file)
        os.remove(tmp_image)
        return None
    else:
        for each in person_result['result']:
            if each[0] == 'person' and each[1] >= 0.98:
                tmp_bbox = list(each[2])
                tmp_bbox.append(each[1])
                person_boxes.append(tmp_bbox)
        if len(person_boxes) == 0:
            os.close(tmp_file)
            os.remove(tmp_image)
            return None
        each_result["num_of_person"] = len(person_boxes)

    # here call the face detection API
    print(datetime.datetime.now(), "call face detection API")
    face_result = requests.post(FACE_DETECT_API, files={'image': (img_url_md5, open(tmp_image).read())}).json()
    print(datetime.datetime.now(), "get the face detection results")
    each_result["face_result"] = face_result
    face_boxes = []
    if face_result["T_F"] is not True:
        os.close(tmp_file)
        os.remove(tmp_image)
        return None
    else:
        for each_face in face_result['result']['boxes']:
            if each_face[4] >= 0.98:
                face_boxes.append(each_face)
        if len(person_boxes) == 0:
            os.close(tmp_file)
            os.remove(tmp_image)
            return None
        each_result["num_of_face"] = len(face_boxes)

    # here get the height and width of image
    real_img = cv2.imread(tmp_image)
    height, width, channels = real_img.shape
    each_result["height"] = height
    each_result["width"] = width

    # here to align the bounding box of face and body
    face_body_align = align_body_face(person_boxes, face_boxes, width, height)
    each_result["result"] = face_body_align
    if face_body_align["is_face_in_body"] == False:
        os.close(tmp_file)
        os.remove(tmp_image)
        return None
    if face_body_align["body_h_percent"] < 0.3 or face_body_align["face_body_h_percent"] > 0.5:
        os.close(tmp_file)
        os.remove(tmp_image)
        return None

    # upload image to cassandra storage
    upload_image(img_url_md5, open(tmp_image, 'rb').read())
    os.close(tmp_file)
    os.remove(tmp_image)

    return each_result


def handle_detail_page(proxy, chrome_options,detail_driver, location_driver, detail_url_md5, detail_link, page_source_ori=None):
    detail_res = {}

    # here to download the detail html page
    if page_source_ori is None:
        try:
            print("download html page: ", detail_link)
            detail_driver.get(detail_link)
            page_source = detail_driver.page_source
        except:
            detail_driver.quit()
            time.sleep(random.randint(1, 2))
            if proxy != "no":
                detail_driver = webdriver.Chrome(chrome_options=chrome_options)
            else:
                detail_driver = webdriver.Chrome()
            detail_driver.set_page_load_timeout(10)
            time.sleep(random.randint(1,2))
            print("detail_driver error and restart")
            detail_driver.get(detail_link)
            page_source = detail_driver.page_source
    else:
        page_source = page_source_ori

    # upload the html page
    upload_html(detail_url_md5, page_source.encode('utf-8'))
    detail_res['detail_link_md5'] = detail_url_md5

    # parse the html page
    parse_res = parse_one_page(page_source)
    for k, v in parse_res.items():
        detail_res[k] = v

    # if has location field
    if detail_res["location_name"] != '':
        # download the location page
        m = hashlib.md5()
        m.update(detail_res["location_url"].encode('utf-8'))
        loc_url_md5 = m.hexdigest()
        loc_info_valid = False
        if if_loc_in_redis(loc_url_md5) == True:
            try:
                loc_info = json.loads(get_loc_info(loc_url_md5))
                for k, v in loc_info.items():
                    result[k] = v
                loc_info_valid = True
            except:
                pass
        if not loc_info_valid:
            try:
                print("location_url: ", detail_res["location_url"])
                location_driver.get('https://www.instagram.com' + detail_res['location_url'])
                page_source = location_driver.page_source
            except:
                #pass
                print("location html download error")

            detail_res["latitude"] = ""
            detail_res["longitude"] = ""
            detail_res["parse_loc_name"] = ""
            detail_res["parse_cc"] = ""
            detail_res["parse_admin1"] = ""
            detail_res["parse_admin2"] = ""
            # parse location html to get latitude and longitude
            for line in page_source.split('\n'):
                if detail_res['latitude'] != "" and detail_res['longitude'] != "":
                    break
                if '<meta property="place:location:' in line:
                    key = line.strip().split(":")[2].split('"')[0]
                    value = line.strip().split('"')[3]
                    detail_res[key] = value

            # lookup latitude and longitude to get the info of this location
            if detail_res["latitude"] != "" and detail_res["longitude"] != "":
                parse_res = rg.search((float(detail_res["latitude"]), float(detail_res["longitude"])))
                parse_res = parse_res[0]
                detail_res["parse_loc_name"] = parse_res["name"]
                detail_res["parse_cc"] = parse_res["cc"]
                detail_res["parse_admin1"] = parse_res["admin1"]
                detail_res["parse_admin2"] = parse_res["admin2"]

                # insert the location info into redis
                inp = {
                    "url": detail_res["location_url"],
                    "location_name": detail_res["location_name"],
                    "longitude": detail_res["longitude"],
                    "latitude": detail_res["latitude"],
                    "parse_loc_name": detail_res["parse_loc_name"],
                    "parse_cc": detail_res["parse_cc"],
                    "parse_admin1": detail_res["parse_admin1"],
                    "parse_admin2": detail_res["parse_admin2"]
                }
                add_loc_info_to_redis(loc_url_md5, json.dumps(inp))

    return detail_res, detail_driver, location_driver


def get_multi_images(proxy, chrome_options, detail_driver, detail_url_md5, detail_link):
    multi_img_res = []

    try:
        print("download html page: ", detail_link)
        detail_driver.get(detail_link)
    except:
        detail_driver.close()
        time.sleep(random.randint(1,2))
        if proxy != "no":
            detail_driver = webdriver.Chrome(chrome_options=chrome_options)
        else:
            detail_driver = webdriver.Chrome()
        detail_driver.set_page_load_timeout(10)
        print("detail_driver error and restart")
        detail_driver.get(detail_link)

    # here download all the images in the detail page
    finish_flag = False
    while not finish_flag:
        each_img_res = None

        try:
            per_img_div = detail_driver.find_element_by_xpath('//div[contains(@class, "tN4sQ zRsZI")]')
        except Exception as e:
            print(e)
            #print("detail_link: %s" %(detail_link))
            #tmp_output = open("error_page", "w")
            #tmp_output.write(detail_driver.page_source)
            #exit()
        per_img = per_img_div.find_element_by_xpath('//div/div/div/img')
        per_img_src = per_img.get_attribute('src')
        if per_img_src is None or per_img_src == "":
            continue
        per_img_alt = per_img.get_attribute('alt')
        if not per_img_alt:
            per_img_alt = ""

        m = hashlib.md5()
        m.update(per_img_src)
        per_img_url_md5 = m.hexdigest()

        each_img_res = filter_image(per_img_src, per_img_url_md5, detail_link)
        if each_img_res is not None:
            multi_img_res.append(each_img_res)

        try:
            next_img_button = per_img_div.find_element_by_xpath('./button[@class="  _6CZji"]')
        except selenium.common.exceptions.NoSuchElementException as e:
            finish_flag = True
            break

        next_img_button.click()
        time.sleep(random.randint(1, 2))

    return multi_img_res, detail_driver, detail_driver.page_source


def main():
    paras = get_cmd()
    proxy = paras.proxy

    user_names = []
    all_data = json.load(open(paras.file))
    all_users = all_data[paras.key]
    start = int(paras.start)
    end = int(paras.end)
    user_names = sorted(all_users)[start:end]

    crawled_user_file = "./data_users/crawled_%d_%d.txt" %(start, end)
    crawled_users = set()
    if os.path.exists(crawled_user_file):
        for line in open(crawled_user_file):
            crawled_users.add(line.strip())
    crawled_user_output = open(crawled_user_file, "a")

    for i, user_name in enumerate(user_names):
        if user_name in crawled_users:
            continue
        url = "https://www.instagram.com/" + user_name + "/"

        # chrome for crawling image list and detail page by tagname
        chrome_options = Options()
        chrome_options.add_argument("--proxy-server=socks5://localhost" + ":" + proxy)
        if proxy != "no":
            browse_driver = webdriver.Chrome(chrome_options=chrome_options)
            detail_driver = webdriver.Chrome(chrome_options=chrome_options)
            location_driver = webdriver.Chrome(chrome_options=chrome_options)
        else:
            browse_driver = webdriver.Chrome()
            detail_driver = webdriver.Chrome()
            location_driver = webdriver.Chrome()
        browse_driver.set_page_load_timeout(10)
        detail_driver.set_page_load_timeout(10)
        location_driver.set_page_load_timeout(10)

        # get image list page
        try:
            browse_driver.get(url)
        except:
            time.sleep(random.randint(1, 2))
            browse_driver.quit()
            if proxy != "no":
                browse_driver = webdriver.Chrome(chrome_options=chrome_options)
            else:
                browse_driver = webdriver.Chrome()
            browse_driver.set_page_load_timeout(10)
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

        finish_flag = False
        output = open("./data_users/%s.txt" %(user_name), "a")
        while not finish_flag:
            print("num: %d, user_name: %s" %(i, user_name))
            #print("\n\n\n user_name %s, cnt_total: %d, cnt_saved_img: %d, cnt_saved_new_img: %d, cnt_saved_html: %d, cnt_saved_new_html: %d" %(user_name, cnt_total, cnt_saved_img, cnt_saved_new_img, cnt_saved_html, cnt_saved_new_html))
            browse_driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.randint(2,4))

            new_height = browse_driver.execute_script("return document.body.scrollHeight")
            # if the scroll reach the end, sroll up a little to mock the website
            if new_height == last_height:
                finish_flag = True
                crawled_users.add(user_name)
                crawled_user_output.write(user_name + "\n")
                continue
            #    time.sleep(random.randint(3, 5))
            #    browse_driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1200);")
            #    continue
            #else:
            #    retry = 0
            last_height = new_height

            # parse the html and get all the images
            imgs = browse_driver.find_elements_by_xpath('//div/div/a/div/div/img')
            print("\n\n\n\ start a new scroll \n\n\n", len(imgs))
            for num, img in enumerate(imgs):
                #try:
                #cnt_total += 1
                result = {}
                result['src_site'] = 'instagram'
                #result['tag'] = tag_name
                result['alt'] = img.get_attribute('alt')
                result['img_src'] = img.get_attribute('src')
                result['detail_link'] = img.find_element_by_xpath('./ancestor::a').get_attribute('href')
                print("original detail link is: ", result['detail_link'])

                m = hashlib.md5()
                m.update(result['img_src'])
                img_url_md5 = m.hexdigest()
                #cnt_saved_img += 1
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
                        # here first judge the type of this posts: single image, multi images, or video
                        result['post_type'] = 'single_img'

                        try:
                            post_type = img.find_element_by_xpath('./ancestor::a/div[@class="u7YqG"]')
                            post_type = post_type.find_element_by_xpath('./span').get_attribute('aria-label')
                            result['post_type'] = post_type
                        except selenium.common.exceptions.NoSuchElementException as e:
                            print("cannot detect post_type")
                        print("post_type: %s" %(result['post_type']))

                        if result['post_type'] == u'视频':
                            print("post_type hit video")
                        elif result['post_type'] == 'single_img':
                            print("hit post_type with single_img")
                            single_img_res = filter_image(result['img_src'], img_url_md5, result['detail_link'])
                            if single_img_res is not None:
                                #cnt_saved_new_img += 1
                                print("single_img_res is not None")
                                for k, v in single_img_res.items():
                                    result[k] = v
                            else:
                                print("single_img_res is None")
                                continue
                            detail_res, detail_driver, location_driver = handle_detail_page(proxy,chrome_options,detail_driver, location_driver, detail_url_md5, result['detail_link'])
                            add_detail_html_to_redis(detail_url_md5, result['detail_link'])
                            for k, v in detail_res.items():
                                result[k] = v
                        elif result['post_type'] == u'轮播':
                            multi_img_res, detail_driver, page_source = get_multi_images(proxy, chrome_options, detail_driver, detail_url_md5, result['detail_link'])
                            add_detail_html_to_redis(detail_url_md5, result['detail_link'])
                            if len(multi_img_res) > 0:
                                result["multi_imgs"] = multi_img_res
                                detail_res, detail_driver, location_driver = handle_detail_page(proxy,chrome_options,detail_driver, location_driver, detail_url_md5, result['detail_link'], page_source_ori=page_source)
                                for k, v in detail_res.items():
                                    result[k] = v
                            else:
                                continue
                        else:
                            print("match none of the options")

                output.write(json.dumps(result).encode("utf-8") + "\n")

        browse_driver.quit()
        detail_driver.quit()
        location_driver.quit()


if __name__ == '__main__':
    main()
