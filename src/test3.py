from src.logic.APICalls import get_multiple_pages, reformat_response

TOKEN = "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"

url = "https://api.github.com/repos/tensorflow/tensorflow/issues/56525/comments"
header = {"Authorization": "Bearer " + TOKEN}
result = get_multiple_pages(url, header)
formatted_result = reformat_response(result)

url2 = "https://api.github.com/repos/tensorflow/tensorflow/pulls/56525/commits"
result2 = get_multiple_pages(url2, header)
formatted_result2 = reformat_response(result2)

url3 = "https://api.github.com/repos/tensorflow/tensorflow/pulls/56525/reviews"
result3 = get_multiple_pages(url3, header)
formatted_result3 = reformat_response(result3)

replies = formatted_result | formatted_result2 | formatted_result3
replies = dict(sorted(replies.items()))

for key_date, value_user in replies.items():
    print(key_date)
    print(value_user)

# pulls = pulls_json("tensorflow", "tensorflow", datetime.datetime(2023, 11, 28), TOKEN)
#
# for pull in pulls:
#     print(pull)
# print(len(pulls))
# print(requests.utils.parse_header_links(pulls.headers['Link']))

# dt = datetime.datetime(2023, 12, 6)
# print(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
