import csv
import os
import boto3
from datetime import datetime, timedelta
import requests

fields = ["stackTrace", "errorValue", "message", "userId", "correlationId", "class", "level", "timestamp"]
file_name = f"cloudwatch_prod_error_logs_{datetime.now().strftime('%Y-%m-%d')}.csv"


def get_error_value_in_string_json(json_string, field):
    start_index = json_string.index(f'{field}')
    # Find the index of the colon that follows the "message" key
    colon_index = json_string.index(':', start_index)
    # Find the index of the first double quote that follows the colon
    quote_index = json_string.index('"', colon_index + 1)
    # Find the index of the second double quote
    try:
        end_quote_index = json_string.index('"', quote_index + 1)
    except:
        end_quote_index = len(json_string)
    # Extract the value of the "message" object
    message = json_string[quote_index + 1:end_quote_index]
    return message.replace(",", " | ")


def get_error_value(json_string, field):
    string_split = json_string.split(":")
    if field == "class":
        return string_split[0].replace(",", " | ")
    elif field == "level":
        return "ERROR"
    elif field == "message":
        if len(string_split) > 1:
            return string_split[1].replace(",", " | ")
    else:
        return ""


def get_cloudwatch_logs():
    client = boto3.client('logs')
    log_group_name = os.getenv("LOG_GROUP_NAME")
    end_time = int(datetime.now().timestamp())
    query = """
    fields @message
    | filter @message like 'ERROR' or @level like 'ERROR'
    | sort @timestamp desc
    """
    response = client.start_query(
        logGroupName=log_group_name,
        startTime=int(datetime.now().timestamp() - timedelta(days=1).total_seconds()),
        endTime=end_time,
        queryString=query,
    )
    query_id = response['queryId']
    response = client.get_query_results(
        queryId=query_id
    )
    error_logs = []
    while response['status'] == 'Running':
        response = client.get_query_results(
            queryId=query_id,
        )
        if response['status'] == 'Complete':
            for error_response in response['results']:
                error_log_json = {}
                response_text = error_response[0]['value'].split("web")[1].replace(":", "", 1).strip()
                error_log_json["stackTrace"] = response_text.replace(",", " | ")
                error_log_json["errorValue"] = error_response
                if response_text[0] == "{":
                    error_log_json["message"] = get_error_value_in_string_json(response_text, "message")
                    error_log_json["userId"] = get_error_value_in_string_json(response_text, "userId")
                    error_log_json["correlationId"] = get_error_value_in_string_json(response_text, "correlationId")
                    error_log_json["class"] = get_error_value_in_string_json(response_text, "class")
                    error_log_json["level"] = get_error_value_in_string_json(response_text, "level")
                    error_log_json["timestamp"] = get_error_value_in_string_json(response_text, "timestamp")
                else:
                    error_log_json["message"] = get_error_value(response_text, "message")
                    error_log_json["userId"] = get_error_value(response_text, "userId")
                    error_log_json["correlationId"] = get_error_value(response_text, "correlationId")
                    error_log_json["class"] = get_error_value(response_text, "class")
                    error_log_json["level"] = get_error_value(response_text, "level")
                    error_log_json["timestamp"] = get_error_value(response_text, "timestamp")
                error_logs.append(error_log_json)
    csv_writer = csv.writer(open(file_name, 'w'))
    csv_writer.writerow(fields)
    for error_log in error_logs:
        csv_writer.writerow(error_log.values())
    return error_logs


def lambda_handler(event, context):
    get_cloudwatch_logs()
    url = os.getenv("SLACK_FILE_UPLOAD_URL")
    payload = {
        'initial_comment': os.getenv("SLACK_COMMENT"),
        'channels': os.getenv("SLACK_CHANNEL"),
    }
    files = {
        "file": [file_name, open("./" + file_name, 'rb'), 'text/csv']
    }
    headers = {
        'Authorization': os.getenv("SLACK_TOKEN")
    }
    return requests.request("POST", url, headers=headers, data=payload, files=files)