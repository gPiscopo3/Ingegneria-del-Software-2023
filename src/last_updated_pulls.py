import datetime
from src.logic.APICalls import filter_pulls_by_date
import time

TOKEN = "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"
header = {"Authorization": "Bearer " + TOKEN}

# Start timer
start_time = time.perf_counter()
pulls = filter_pulls_by_date("tensorflow", "tensorflow", datetime.datetime(2023, 11, 10), TOKEN)

for pull in pulls:
    print(pull)

print(len(pulls))

# url = list()
# i = len(pulls) - 1
# while i > -1:
#     url.append(pulls[i]["_links"]["comments"]["href"])
#     url.append(pulls[i]["_links"]["review_comments"]["href"])
#     url.append(pulls[i]["_links"]["commits"]["href"])
#     url.append(pulls[i]["url"] + '/reviews')
#     i = i - 1
#
# fully_merged_replies = dict()
# for u in url:
#     # print(u)
#     replies = reformat_response(get_multiple_pages(u, header))
#     i = 0
#     for key, value in replies.items():
#         if key > datetime.datetime(2023, 10, 23):
#             i = i + 1
#     if len(replies) > 0:
#         print(str(i) + ' ' + str(len(replies)) + ' percentage: ' + str(i/len(replies)))
#     else:
#         print(str(i) + ' ' + str(len(replies)))
#
#     fully_merged_replies = fully_merged_replies | replies
#
# fully_merged_replies = dict(sorted(fully_merged_replies.items()))
# j = 0
# for key_date, value_user in fully_merged_replies.items():
#     if key_date > datetime.datetime(2023, 10, 23):
#         j = j + 1
#
#
# if len(fully_merged_replies) > 0:
#     print(str(j) + ' su ' + str(len(fully_merged_replies)) + ' percentage: ' + str(j/len(fully_merged_replies)))
# else:
#     print(str(j) + ' su ' + str(len(fully_merged_replies)))
#
#
# # End timer
# end_time = time.perf_counter()
#
# elapsed_time = end_time - start_time
# print("Elapsed time: ", elapsed_time)


# replies = dict(sorted(replies.items()))
# for key_date, value_user in replies.items():
#     print(key_date)
#     print(value_user)
