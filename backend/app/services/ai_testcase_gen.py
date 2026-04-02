import pypandoc
import requests
import json
import urllib3
import sseclient
import os
import time
from random import choice
from hashlib import md5
from string import digits,ascii_letters
import re

    
def doc_to_markdown_string(doc_path):
    """
    将doc/docx文件转换为markdown字符串
    """
    try:
        # 使用pandoc进行转换
        output = pypandoc.convert_file(doc_path, 'md', format='docx')
        return output
    except Exception as e:
        return f"转换出错: {str(e)}"

###############使用key和secret生成token###############
def generate_token(api_key, api_secret, url="https://copilot.glodon.com/api/auth/v1/access-token"):
    """
    生成token
    
    :param api_key: 租户的API Key，必填项
    :param api_secret: 租户的API Secret，必填项
    :param url: 请求的接口地址, 默认为内网url
    :returns: 返回token
    """
    if api_key == "" or api_secret == "":
        print("请输入api_key和api_secret")
        return ""
    
    nowtime = time.time()
    timestamp = str(int(nowtime * 1000))
    noncestr = generate_random_str(24)
    raw_token = api_key + ":" + timestamp + ":" + noncestr + ":" + api_secret
    auth = generate_md5(raw_token)
    payload = {}
    headers = {
    'X-AIOT-APIKEY': api_key,
    'X-AIOT-TIMESTAMP': timestamp,
    'X-AIOT-NONCESTR': noncestr,
    'Authorization': "Basic " + auth
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            res = response.json()
            if res["code"] != 200:
                raise Exception(res["message"])

            token ="Bearer " + res["data"]["accessToken"]
            return (token)
        else:
            raise Exception(response.status_code)
    except Exception as err:
        print('An exception happened: ' + str(err))
        return ""

def generate_md5(src):
    m = md5(src.encode(encoding='utf-8'))
    return m.hexdigest()

def generate_random_str(randomlength=24):
    str_list = [choice(digits + ascii_letters) for i in range(randomlength)]
    random_str = ''.join(str_list)
    return random_str


###############上传文件并获得URL###############
def upload_files(basetoken, uploadurl,filepath):
    with open(filepath, "rb") as f:
        files = {"file": f}
        data  = {"purpose": "infer"}
        headers = {"Authorization": basetoken}
        response = requests.post(uploadurl, files=files, data=data, headers=headers)
    if response.status_code == 200:
        res = response.json()
        if res["code"] != 200:
            raise Exception(res["message"])

        file_url= res["data"]["url"]
        print(file_url)
        return file_url
    else:
        raise Exception(response.status_code)






def excute_test_gen():

    ##生成token
    api_key = "hxHkv8BS0a1MDlsL"
    api_secret = "1X51L2RULJuTGyY0x18uss1p"
    host="https://copilot.glodon.com"
    get_token_api="/api/auth/v1/access-token"
    get_token_url = host+get_token_api
    base_token = generate_token(api_key, api_secret, get_token_url)

    ##异步调用工作流-需求点生成

    workflow_URL = "https://copilot.glodon.com/api/cvforce/aishop/v1/chat/completions"
    payload = json.dumps({
        "model": "Arulkqtcfw04k",
        "messages": [
        {
            "role": "user",
            "content": "你好"
        }
        ],
        "stream": False,
        "max_tokens": 8000,
        "temperature": 0.5,
        "top_p": 0.8,
        "top_k": 50,
        "repetition_penalty": 1.05
        })
    headers = {
    'Authorization': base_token,
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", workflow_URL, headers=headers, data=payload)
 
    print(json.dumps(response.text, ensure_ascii=False, indent=4))
excute_test_gen()