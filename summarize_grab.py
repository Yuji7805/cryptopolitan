import sqlite3
import openai
from datetime import datetime, timedelta
import requests
import time
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GRAB_API_KEY')
MESSAGESIZE = 2000
PROMPT = os.getenv("PROMPT")

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
def summarize_large_text(content, prompt=PROMPT):
    if len(content.split()) <= MESSAGESIZE:
        return summarize_by_gpt35(content)
    chunks = divide_text(content, MESSAGESIZE)
    summarized_parts = []
    print("large text length: ", len(chunks))
    for chunk in chunks:
        summarized_text = summarize_by_gpt35(chunk, prompt)
        summarized_parts.append(summarized_text)
    summary = ' '.join(summarized_parts)
    summary = summarize_by_gpt35(summary)
    return summary


def summarize_by_gpt35(content, prompt=PROMPT):
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


def create_table():
    connect_db()
    c.execute('''CREATE TABLE IF NOT EXISTS articles
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT,
                publish_date DATE,
                category TEXT,
                currency TEXT,
                title TEXT,
                content TEXT,
                summary TEXT,
                link TEXT)''')
    close_db_connection()


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
        c.execute("INSERT INTO articles (author, publish_date, category, currency, title, content, summary, link) VALUES (?,?,?,?,?,?,?,?)",
                  (article["author"], article["publish_date"], article["category"], article["currency"], article["title"], article["content"], article["summary"], article["link"]))
        conn.commit()
        inserted_dates[article['publish_date']] = 1
        close_db_connection()


def close_db_connection():
    conn.close()


create_table()
print("table created")
