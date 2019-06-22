# fashion_crawler
This is a project for crawling fashion images and associate information from online resources.

### Requirements
1. python
2. sudo apt-get install python-pip python-dev libmysqlclient-dev
3. pip install:
   opencv-python, simplejson, redis, selenium, requests, bs4, mysqlclient, python-dateutil, pyyaml, reverse_geocoder, lxml 
4. install chromedriver for selenium:
   wget https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip
   unzip chromedriver_linux64.zip
   sudo mv chromedriver /usr/bin/chromedriver
   sudo chmod +x /usr/bin/chromedriver
5. serveral API resources which will be released later. They are basically for image/html storage, human body detection, face detection, and image quality assess.

### Usage
#### Crawl by Locations
In the current version, we aim to crawl data from 14 cities from all over the world. We manually identify the instagram url for each city, and then for each city we use two browser drivers to conduct the crawling.
Since for all the 14 cities there emerge tens of thousands instagram posts everyday, it is impossible for us to collect all the posts. However, we want to continously observe the fashion trends for all the locations, which means we should get the updated data. Thus, we employ a naive but effective approach: restart the cralwer everyday, then at least for each day we can get some posts.
Even though the idea is simple, but it is not easy to restart all the processes everyday manually. So we write two auxilary scripts start.sh and stop.sh to help us do those annoying work. What's more, by putting those two scripts in cron table, we can restart the crawler at any time interval.

start: bash start.sh
stop: bash stop.sh

if you want to set crontab to restart the crawler everyday, run the command `crontab -e`, and refer to crontab.txt. Note that, it is better to start the cralwer in 5 minutes later. 
