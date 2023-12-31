import time
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import summarize_grab as sg
import os

import logging

# Configure the logging module
logging.basicConfig(filename='log.txt', level=logging.INFO)

URL = "https://www.cryptopolitan.com/feed/"
PROMPT = os.getenv('PROMPT')


def convert_to_xml(data_str):
    root = ET.fromstring(data_str)
    return root


def convert_date_from_string(date_str):
    date_obj = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    return date_obj.strftime("%Y-%m-%d %H:%M:%S")


def record_article_by_feed(interval):
    sg.init_inserted_times()
    while True:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36"
            }
            response = requests.get(URL, headers=headers)
            feed = convert_to_xml(response.text)
            print("article updated", datetime.utcnow())            
            items = feed.findall('.//item')
            for item in items:
                pubDate = convert_date_from_string(
                    item.find('.//pubDate').text)
                print(sg.registered(pubDate), pubDate)                

                if not sg.registered(pubDate):
                    title = item.find('.//title').text
                    link = item.find('.//link').text
                    dc_creator = item.find(
                        '{http://purl.org/dc/elements/1.1/}creator').text
                    print("author: ", dc_creator)
                    print("title: ", title)
                    print("link: ", link)
                    logging.info("author: ", dc_creator)
                    logging.info("title: ", title)
                    logging.info("link: ", link)
                    category = []
                    categories = item.findall('.//category')
                    for cate in categories:
                        category.append(cate.text)
                    category = ', '.join(category)
                    print("category: ", category)
                    logging.info("category: ", category)
                    content = item.find(
                        '{http://purl.org/rss/1.0/modules/content/}encoded').text
                    content = re.sub('<[^<]+?>', '', content)

                    summary = sg.summarize_large_text(content, PROMPT)
                    print(content)
                    print("#"*150)
                    logging.info(content)
                    logging.info("#"*150)
                    article = {
                        "author": dc_creator,
                        "title": title,
                        "category": category,
                        "currency": "crypto",
                        "publish_date": pubDate,
                        "content": content,
                        "summary": summary,
                        "link": link
                    }
                    sg.insert_article(article)
                time.sleep(0.15)
            time.sleep(interval)
        except requests.exceptions.ConnectionError as e:
            print("Error: ", e)
            print("Retrying in 5 seconds...")
            logging.info("Error: ", e)
            logging.info("Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print("Extra Error: ", e)
            logging.info("Extra Error: ", e)
            return


interval = open("time.ini")
interval = int(interval.readline())
print(interval)
record_article_by_feed(interval)
