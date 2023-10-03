import sqlite3
import openai
from datetime import datetime, timedelta
import requests
import time
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('API_KEY')
MESSAGESIZE = 1600
prompt1 = os.getenv('PROMPT')
conn = None
c = None
mutex_load_articles = True


def connect_db():
    global conn
    global c
    conn = sqlite3.connect("articles.db")
    c = conn.cursor()


openai.api_key = api_key
current_inserted_date = ''
inserted_dates = {}


def rate_limited(max_per_second):
    min_interval = 1.0 / float(max_per_second)

    def decorate(func):
        last_time_called = 0.0

        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            nonlocal last_time_called
            elapsed = time.perf_counter() - last_time_called
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            last_time_called = time.perf_counter()
            return func(*args, **kwargs)
        return rate_limited_function
    return decorate


def divide_text(text, n):
    words = text.split()
    return [' '.join(words[i:i+n]) for i in range(0, len(words), n)]


@rate_limited(0.03)
def summarize_large_text(content, prompt=prompt1):
    if len(content.split()) <= MESSAGESIZE:
        return summarize_by_gpt35(content, prompt)
    chunks = divide_text(content, MESSAGESIZE)
    summarized_parts = []
    print("large text length: ", len(chunks))
    for chunk in chunks:
        summarized_text = summarize_by_gpt35(chunk, prompt)
        summarized_parts.append(summarized_text)
    summary = ' '.join(summarized_parts)
    summary = summarize_by_gpt35(summary, prompt)
    return summary


def summarize_by_gpt35(content, prompt=prompt1):
    print(prompt)
    instructions_to_the_model = f"{prompt}\n\n{content}"
    while True:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": instructions_to_the_model},
                ]
            )
            summary = response['choices'][0]['message']['content']
            print("gpt3.5")
            return summary
        except requests.exceptions.ConnectionError as e:
            print("Error: ", e)
            print("Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print("Extra Error: ", e)
            return


def get_publish_dates():
    connect_db()
    query = "SELECT publish_date FROM articles"
    c.execute(query)
    dates = c.fetchall()
    close_db_connection()
    return dates


def init_inserted_times():
    global inserted_dates
    dates = get_publish_dates()
    print(len(dates))
    for date in dates:
        inserted_dates[date[0]] = 1


def registered(publish_date):
    try:
        val = inserted_dates[publish_date]
        return True
    except:
        return False


def insert_article(article):
    global current_inserted_date
    current_inserted_date = article['publish_date']
    global inserted_dates
    init_inserted_times()
    if not registered(article['publish_date']):
        connect_db()
        c.execute("INSERT INTO articles (author, publish_date, category, currency, title, content, summary, link) VALUES (?,?,?,?,?,?,?)",
                  (article["author"], article["publish_date"], article["category"], article["currency"], article["title"], article["content"], article["summary"], article["link"]))
        conn.commit()
        inserted_dates[article['publish_date']] = 1
        close_db_connection()


def load_all_categories():
    cat_dic = {}
    connect_db()
    query = f"SELECT category FROM articles"
    c.execute(query)
    categories = c.fetchall()
    for each in categories:
        for one in each:
            for cat in one.split(", "):
                cat_dic[cat] = 1
    cat_list = list(cat_dic.keys())
    cat_list.sort()
    close_db_connection()
    return ', '.join(cat_list)


def load_articles(currency, category, period=0, start_date="1900-01-01 00:00:00", end_date="5000-12-12 23:59:59"):
    global mutex_load_articles
    mutex_load_articles = False
    connect_db()
    end_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    end_date = datetime.strptime((end_date), '%Y-%m-%d %H:%M:%S')
    print(end_date)
    _category = category
    if "Industry News" in category:
        _category = "Industry News"
        if period > 72:
            period = 72
    if "Trending News" in category:
        if period > 72:
            period = 72
    if period == 0:
        period = 168
    start_date = end_date - timedelta(hours=period)
    start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date = end_date.strftime(('%Y-%m-%d %H:%M:%S'))
    query = f"SELECT * FROM articles WHERE category LIKE '%{_category}%' AND publish_date BETWEEN '{start_date}' AND '{end_date}'"
    c.execute(query)
    articles_all = c.fetchall()
    articles_news = []
    articles_gaming = []
    if "Industry News" in category:
        for article in articles_all:
            if "Gaming" in article[3]:
                articles_gaming.append(article)
            else:
                articles_news.append(article)
    articles = ''
    if "Gaming" in category:
        articles = articles_gaming
    elif "Industry News" in category:
        articles = articles_news
    else:
        articles = articles_all
    close_db_connection()
    mutex_load_articles = True
    return articles


# def load_article_links(currency, category, period=0, start_date="1900-01-01 00:00:00", end_date="5000-12-12 23:59:59"):
#     global mutex_load_articles
#     mutex_load_articles = False
#     connect_db()
#     end_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
#     end_date = datetime.strptime((end_date), '%Y-%m-%d %H:%M:%S')
#     print(end_date)
#     if period == 0:
#         period = 168
#     start_date = end_date - timedelta(hours=period)
#     start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
#     end_date = end_date.strftime(('%Y-%m-%d %H:%M:%S'))
#     query = f"SELECT link FROM articles WHERE category LIKE '%{category}%' AND publish_date BETWEEN '{start_date}' AND '{end_date}'"
#     c.execute(query)
#     links = c.fetchall()
#     close_db_connection()
#     mutex_load_articles = True
#     return links


def summarize_articles(articles, prompt):
    contents = ''
    for article in articles:
        contents += article[2] + "\n" + article[7]
    return summarize_large_text(contents, prompt)


def get_content_by_link(link):
    connect_db()
    c.execute("SELECT content FROM articles WHERE link=?", (link,))
    content = c.fetchone()
    close_db_connection()
    return content


def get_summary_by_link(link):
    connect_db()
    c.execute("SELECT summary FROM articles WHERE link=?", (link,))
    summary = c.fetchone()
    close_db_connection()
    return summary

def get_time_by_link(link):
    connect_db()
    c.execute("SELECT publish_date FROM articles WHERE link=?", (link,))
    publish_date = c.fetchone()
    close_db_connection()
    return publish_date


def close_db_connection():
    conn.close()
