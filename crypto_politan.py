import time
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import summarize_api as sa


URL = "https://www.cryptopolitan.com/feed/"


def convert_to_xml(data_str):
    root = ET.fromstring(data_str)
    return root


def convert_date_from_string(date_str):
    date_obj = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    return date_obj.strftime("%Y-%m-%d %H:%M:%S")


def record_article_by_feed(interval):
    sa.init_inserted_times()
    while True:
        try:
            response = requests.get(URL)
            feed = convert_to_xml(response.text)
            print("article updated")
            items = feed.findall('.//item')
            for item in items:
                pubDate = convert_date_from_string(
                    item.find('.//pubDate').text)
                print(sa.registered(pubDate), pubDate)
                if not sa.registered(pubDate):
                    title = item.find('.//title').text
                    print("title: ", title)
                    link = item.find('.//link').text
                    print("link: ", link)
                    dc_creator = item.find(
                        '{http://purl.org/dc/elements/1.1/}creator').text
                    print("author", dc_creator)
                    category = []
                    categories = item.findall('.//category')
                    for cate in categories:
                        category.append(cate.text)
                    category = ', '.join(category)
                    print("category: ", category)
                    content = item.find(
                        '{http://purl.org/rss/1.0/modules/content/}encoded').text
                    content = re.sub('<[^<]+?>', '', content)
                    summary = sa.summarize_large_text(content)
                    print(content)
                    print("#"*150)
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
                    sa.insert_article(article)
                time.sleep(0.2)
            time.sleep(interval)
        except requests.exceptions.ConnectionError as e:
            print("Error: ", e)
            print("Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print("Extra Error: ", e)
            return


def record_article_by_link(link, insertMode=True):
    while True:
        try:
            article = {}
            response = requests.get(link, headers={
                "User-Agent": "PostmanRuntime/7.28.4",
            })
            from lxml import html
            tree = html.fromstring(response.text)
            title = tree.xpath(
                "/html/body/div[1]/div/div/main/div/div[1]/article/div[2]/header/h1")[0].text_content().strip()
            content = tree.xpath(
                "/html/body/div[1]/div/div/main/div/div[1]/article/div[2]/div[3]/div[2]")[0].text_content().strip()
            
            # content = content.split("Read more")[1]
            if not insertMode:
                return content
            content = sa.summarize_large_text(content)
            dc_creator = tree.xpath(
                "/html/body/div[1]/div/div/main/div/div[1]/article/div[2]/header/div[2]/div[1]/a/span")[0].text_content().strip()

            script = tree.xpath(
                "//script[contains(., 'datePublished')]/text()")[0]
            import json
            data = json.loads(script)
            pubDate = data['@graph'][0]['datePublished']
            date_object = datetime.strptime(pubDate, "%Y-%m-%dT%H:%M:%S%z")
            pubDate = date_object.strftime("%Y-%m-%d %H:%M:%S")

            category_meta = tree.xpath('/html/head')[0]
            meta_tags = [element for element in category_meta.iterdescendants()
                         if element.tag == 'meta']

            category = []
            for meta_tag in meta_tags:
                if meta_tag.get('property') == 'article:tag' or meta_tag.get('property') == 'article:section':
                    category.append(meta_tag.get('content'))
            category = ', '.join(category)

            article = {
                "author": dc_creator,
                "title": title,
                "category": category,
                "currency": "crypto",
                "publish_date": pubDate,
                "summary": content,
                "link": link
            }
            print("inserting article...")
            sa.insert_article(article)
            return article
        except requests.exceptions.ConnectionError as e:
            print("Error: ", e)
            print("Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print("Extra Error: ", e)
            return
