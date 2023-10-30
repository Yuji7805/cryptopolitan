import itertools
import aiohttp
import asyncio
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


API_KEYS = ["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",
            "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",
            "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",
            "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",
            "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",
            "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",
            "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",
            "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",
            "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"]


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


@rate_limited(1.0)
async def summarize_large_text(content, prompt=prompt1):
    if len(content.split()) <= MESSAGESIZE:
        return summarize_by_gpt35(content, prompt)

    chunks = divide_text(content, MESSAGESIZE)
    summarized_parts = []
    print("large text length: ", len(chunks))
    print("doign tasks")
    tasks = [summarize_by_gpt35_async(chunk, prompt) for chunk in chunks]
    # Run the tasks concurrently
    print("merging results")
    summarized_results = await asyncio.gather(*tasks)
    # summarized_results = await summarized_results_future
    for result in summarized_results:
        summarized_parts.append(result)
    print("summarizing merged result...")
    summary = ' '.join(summarized_parts)
    summary = await summarize_large_text(summary, prompt)
    print("last summarizing finished")
    return summary


async def summarize_by_gpt35_async(content, prompt=prompt1):
    print(prompt)
    instructions_to_the_model = f"{prompt}\n\n{content}"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                api_key = get_next_api_key()  # Obtain the next API key from the available keys
                print(api_key)
                response = await session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": instructions_to_the_model},
                        ]
                    },
                )

                data = await response.json()
                summary = data['choices'][0]['message']['content']
                print("gpt3.5 async", len(summary))
                return summary
            except aiohttp.ClientConnectionError as e:
                print("Error: ", e)
                print("Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print("Extra Error: ", e)
                return

api_key_generator = itertools.cycle(API_KEYS)


def get_next_api_key():
    return next(api_key_generator)


def summarize_by_gpt35(content, prompt=prompt1):
    # print(prompt, content)
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
            print("gpt3.5 sync")
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


def load_all_categories():
    cat_dic = {}
    connect_db()
    end_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    end_date = datetime.strptime((end_date), '%Y-%m-%d %H:%M:%S')

    start_date = end_date - timedelta(hours=72)
    start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date = end_date.strftime(('%Y-%m-%d %H:%M:%S'))
    print(start_date, end_date)

    query = f"SELECT category FROM articles WHERE publish_date BETWEEN '{start_date}' AND '{end_date}'"
    c.execute(query)
    categories = c.fetchall()
    for each in categories:
        for one in each:
            if "Industry News" in one:
                cat_dic[one] = 1
            else:
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
        period = 72
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
            if "Gaming" in article[3] or "game" in article[3]:
                articles_gaming.append(article)
            else:
                articles_news.append(article)
    articles = ''
    if "Blockchain Gaming" in category or "Gaming Hardware" in category:
        articles = articles_all
    elif "Gaming" in category or "game" in category:
        articles = articles_gaming
    elif "Industry News" in category:
        articles = articles_news
    else:
        articles = articles_all
    close_db_connection()
    mutex_load_articles = True
    return articles


async def summarize_articles(articles, prompt):
    contents = ''
    for article in articles:
        contents += article[2] + "\n" + article[7]
    # asyncio.set_event_loop_policy(
    #     asyncio.WindowsSelectorEventLoopPolicy())  # Only required on Windows
    return await summarize_large_text(contents, prompt)


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


# delete record that has blank field
# connect_db()
# query = "DELETE FROM articles WHERE author IS NULL OR publish_date IS NULL OR category IS NULL OR currency IS NULL OR title IS NULL OR content IS NULL OR summary IS NULL OR link IS NULL"
# c.execute(query)
# conn.commit()
# close_db_connection()
