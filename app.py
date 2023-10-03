from flask import request, jsonify, Flask, make_response, render_template, send_from_directory
import summarize_api as sa
import crypto_politan as cp
from flask_cors import CORS
import time
import os

PROMPT = os.getenv("PROMPT")
prompt2 = PROMPT


def summarize_recent_articles(period, category, currency):
    while True:
        if sa.mutex_load_articles:
            sa.mutex_load_articles = False
            articles = sa.load_articles(
                "crypto", category, period=period)
            links = []
            for each in articles:
                print(each)
                links.append(each[8])
            if len(articles) == 0:
                return "No matching content", " "
            if len(articles) == 1:
                return articles[0][7], ', '.join(links)
            print("#" * 150)
            summary = sa.summarize_articles(articles, prompt2)
            links = ', '.join(links)
            return summary, links
        else:
            time.sleep(0.1)


# def test_get_article_links(period, category):
#     while True:
#         if sa.mutex_load_articles:
#             sa.mutex_load_articles = False
#             articles = sa.load_article_links(
#                 "crypto", category, period=period)
#             links = []
#             for each in articles:
#                 links.append(each[0])
#             if len(articles) == 0:
#                 return " "
#             if len(articles) == 1:
#                 print(links)
#                 return ', '.join(links)
#             print("#" * 150)
#             print(links)
#             links = ', '.join(links)
#             return links
#         else:
#             time.sleep(0.1)


def get_article_contents_by_links(article_links):
    print(article_links)
    contents = []
    for link in article_links:
        print("article link: ", link)
        content = cp.record_article_by_link(link, insertMode=False)
        print("=======> ", content)
        contents.append(content)

    print("raw content captured!")
    return "\n".join(contents)


app = Flask(__name__)
CORS(app)


@app.route('/api/v1/article-num', methods=['POST', 'OPTIONS'])
def get_article_num():
    if sa.mutex_load_articles:
        sa.mutex_load_articles = False
        req_json = request.json
        period = int(req_json['period'])
        category = req_json['category']
        print(period, " hours, and related to ==> ", category)

        articles = sa.load_articles(
            "crypto", category, period=period)
        res = len(articles)
        response = make_response(jsonify({"article num": res}))
        return response


@app.route('/api/v1/insert-article-by-link', methods=['POST', 'OPTIONS'])
def insert_article_by_link():
    req_json = request.json
    link = req_json['link']
    response = None
    try:
        article = cp.record_article_by_link(link)
        response = make_response(
            jsonify({"accepted": 'article recorded', "article": article}))
        response.status_code = 200
    except:
        response = make_response(jsonify({"msg": 'err in recoding'}))
        response.status_code = 500
    return response


@app.route('/api/v1/summarize-articles', methods=['POST', 'OPTIONS'])
def sum_articles():
    response = None
    try:
        req_json = request.json
        period = req_json['period']
        category = req_json['category']
        # currency = req_json['currency']
        summary, links = summarize_recent_articles(
            int(period), category, "crypto")
        response = make_response(jsonify({"summary": summary, "link": links}))
        response.status_code = 200
        return response
    except KeyError:
        response = make_response(jsonify({'msg': "bad request"}))
        response.status_code = 400
    except TypeError:
        response = make_response(jsonify({'msg': "bad request"}))
        response.status_code = 400
    except Exception as exc:
        response = make_response(jsonify({'msg': exc}))
        response.status_code = 500
    return response


@app.route('/api/v1/get-category', methods=['GET', 'OPTIONS'])
def get_category():
    categories = sa.load_all_categories()
    response = make_response(jsonify({"category": categories}))
    return response


# @app.route('/api/v1/test-get-article-link', methods=['POST', 'OPTION'])
# def test_get_article_link():
#     req_json = request.json
#     period = int(req_json['period'])
#     category = req_json['category']
#     response = None
#     article_links = test_get_article_links(period, category)
#     response = make_response(jsonify({"link": article_links}))
#     return response


@app.route("/api/v1/prompt", methods=["GET", "Options"])
def get_prompt():
    response = make_response(jsonify({"prompt": PROMPT}))
    return response


# @app.route("/api/v1/summarize-by-links", methods=["POST", "Options"])
# def summzrize_by_links():
#     req_json = request.json
#     prompt = req_json['prompt']
#     links = req_json['links'].split(', ')
#     print("summarizing from raw article...")
#     summary = sa.summarize_large_text(
#         get_article_contents_by_links(links), prompt)
#     print("@"*111)
#     print(summary)
#     print("@"*111)
#     response = make_response(jsonify({"summary": summary}))
#     return response


@app.route("/")
def home():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8091)
